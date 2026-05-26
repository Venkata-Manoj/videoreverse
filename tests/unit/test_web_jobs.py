from __future__ import annotations

import json
import os
import tempfile

import pytest

from web.db import Database
from web.jobs import JobManager


@pytest.fixture
def tmp_db_path() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def db(tmp_db_path: str) -> Database:
    return Database(db_path=tmp_db_path)


def test_job_manager_create_and_get(db: Database) -> None:
    mgr = JobManager(db)
    job_id = mgr.create_job()
    assert job_id is not None and len(job_id) == 12
    job = mgr.get_job(job_id)
    assert job is not None
    assert job["id"] == job_id
    assert job["status"] == "pending"


def test_job_manager_update_status(db: Database) -> None:
    mgr = JobManager(db)
    job_id = mgr.create_job()
    db.update_job_status(job_id, "running")
    job = mgr.get_job(job_id)
    assert job["status"] == "running"


def test_job_manager_update_status_with_result(db: Database) -> None:
    mgr = JobManager(db)
    job_id = mgr.create_job()
    result = {"mode": "single", "blueprint": {"global_aesthetic": {"style": "cinematic"}}}
    db.update_job_status(job_id, "complete", result=result)
    job = mgr.get_job(job_id)
    assert job["status"] == "complete"
    assert job["result"]["mode"] == "single"
    assert job["result"]["blueprint"]["global_aesthetic"]["style"] == "cinematic"


def test_job_manager_update_status_with_error(db: Database) -> None:
    mgr = JobManager(db)
    job_id = mgr.create_job()
    db.update_job_status(job_id, "error", error="VR-203: Gemini synthesis failed")
    job = mgr.get_job(job_id)
    assert job["status"] == "error"
    assert "VR-203" in job["error"]


def test_job_manager_tracks_artifact_files(db: Database) -> None:
    mgr = JobManager(db)
    job_id = mgr.create_job()
    db.update_job_status(job_id, files={"json": "/tmp/output.json", "txt": "/tmp/output.txt"})
    job = mgr.get_job(job_id)
    assert job["files"]["json"] == "/tmp/output.json"
    assert job["files"]["txt"] == "/tmp/output.txt"


def test_job_manager_append_files(db: Database) -> None:
    mgr = JobManager(db)
    job_id = mgr.create_job()
    db.update_job_status(job_id, files={"json": "/tmp/output.json"})
    db.update_job_status(job_id, files={"txt": "/tmp/output.txt"})
    job = mgr.get_job(job_id)
    assert job["files"]["json"] == "/tmp/output.json"
    assert job["files"]["txt"] == "/tmp/output.txt"


def test_job_manager_pushes_events(db: Database) -> None:
    mgr = JobManager(db)
    job_id = mgr.create_job()
    mgr._push_event(job_id, "step", {"message": "Ingesting video"})
    events = db.get_events(job_id)
    assert len(events) == 1
    assert events[0]["event"] == "step"
    assert events[0]["data"]["message"] == "Ingesting video"


def test_job_manager_sse_stream_for_nonexistent_job(db: Database) -> None:
    mgr = JobManager(db)
    events = list(mgr.iter_events("nonexistent"))
    assert len(events) == 1
    payload = json.loads(events[0].removeprefix("data: ").strip())
    assert payload["event"] == "error"
    assert payload["message"] == "Job not found"


def test_job_manager_get_nonexistent_job(db: Database) -> None:
    mgr = JobManager(db)
    assert mgr.get_job("nonexistent") is None


def test_job_manager_count_jobs(db: Database) -> None:
    mgr = JobManager(db)
    assert mgr.count_jobs() == 0
    mgr.create_job()
    mgr.create_job()
    assert mgr.count_jobs() == 2


# --- Database edge cases ---

def test_db_empty_events_for_valid_job(db: Database) -> None:
    job_id = db.create_job()
    events = db.get_events(job_id)
    assert events == []


def test_db_get_events_after_id(db: Database) -> None:
    job_id = db.create_job()
    db.add_event(job_id, "step1", {"n": 1})
    db.add_event(job_id, "step2", {"n": 2})
    later = db.get_events(job_id, after_id=1)
    assert len(later) == 1
    assert later[0]["event"] == "step2"


def test_db_list_jobs_empty(db: Database) -> None:
    assert db.list_jobs() == []


def test_db_list_jobs_ordering(db: Database) -> None:
    a = db.create_job()
    b = db.create_job()
    c = db.create_job()
    jobs = db.list_jobs()
    assert len(jobs) == 3
    assert jobs[0]["id"] == c
    assert jobs[-1]["id"] == a


def test_db_update_status_with_only_files(db: Database) -> None:
    job_id = db.create_job()
    db.update_job_status(job_id, files={"json": "out.json"})
    job = db.get_job(job_id)
    assert job["status"] == "pending"
    assert job["files"]["json"] == "out.json"


def test_db_update_status_with_only_result(db: Database) -> None:
    job_id = db.create_job()
    db.update_job_status(job_id, result={"key": "val"})
    job = db.get_job(job_id)
    assert job["status"] == "pending"
    assert job["result"]["key"] == "val"


def test_db_get_job_files_before_set(db: Database) -> None:
    job_id = db.create_job()
    assert db.get_job_files(job_id) == {}


def test_db_get_job_files_nonexistent(db: Database) -> None:
    assert db.get_job_files("ghost") == {}


def test_db_delete_old_jobs_removes_old_entries(db: Database) -> None:
    job_id = db.create_job()
    import time
    db._conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (1.0, job_id))
    db._conn.commit()
    deleted = db.delete_old_jobs(max_age_hours=0)
    assert deleted >= 1
    assert db.get_job(job_id) is None


def test_db_delete_old_jobs_preserves_recent(db: Database) -> None:
    job_id = db.create_job()
    deleted = db.delete_old_jobs(max_age_hours=24)
    assert deleted == 0
    assert db.get_job(job_id) is not None


def test_db_create_job_with_custom_id(db: Database) -> None:
    jid = db.create_job("my-custom-id")
    assert jid == "my-custom-id"
    assert db.get_job(jid) is not None


def test_db_special_chars_in_event_data(db: Database) -> None:
    job_id = db.create_job()
    db.add_event(job_id, "log", {"msg": "héllo wörld 🌍! 测试"})
    events = db.get_events(job_id)
    assert events[0]["data"]["msg"] == "héllo wörld 🌍! 测试"


def test_db_multiple_updates_accumulate(db: Database) -> None:
    job_id = db.create_job()
    db.update_job_status(job_id, "running")
    db.update_job_status(job_id, "complete", result={"ok": True})
    db.update_job_status(job_id, files={"json": "out.json"})
    job = db.get_job(job_id)
    assert job["status"] == "complete"
    assert job["result"]["ok"] is True
    assert job["files"]["json"] == "out.json"


# --- JobManager edge cases ---

def test_job_manager_list_jobs(db: Database) -> None:
    mgr = JobManager(db)
    assert mgr.list_jobs() == []
    mgr.create_job()
    assert len(mgr.list_jobs()) == 1


def test_job_manager_events_in_ss_stream_order(db: Database) -> None:
    mgr = JobManager(db)
    job_id = mgr.create_job()
    mgr._push_event(job_id, "a", {"i": 0})
    mgr._push_event(job_id, "b", {"i": 1})
    mgr._push_event(job_id, "c", {"i": 2})
    db_events = db.get_events(job_id)
    assert [e["event"] for e in db_events] == ["a", "b", "c"]


def test_job_manager_cleanup_does_not_remove_recent(db: Database) -> None:
    mgr = JobManager(db)
    mgr.create_job()
    mgr.create_job()
    assert mgr.count_jobs() == 2
    mgr.cleanup_old_jobs(max_age_hours=24)
    assert mgr.count_jobs() == 2


def test_job_manager_count_after_cleanup(db: Database) -> None:
    import time
    mgr = JobManager(db)
    jid = mgr.create_job()
    db._conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (1.0, jid))
    db._conn.commit()
    mgr.cleanup_old_jobs(max_age_hours=0)
    assert mgr.count_jobs() == 0
