from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from src.path_resolver import get_root


DEFAULT_DB_PATH = f"{get_root()}/.cache/videoreverse.db"


def _get_db_path() -> str:
    return os.environ.get("VIDEO_REV_DB_PATH", DEFAULT_DB_PATH)


class Database:
    def __init__(self, db_path: str | None = None) -> None:
        self._path = db_path or _get_db_path()
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT,
                error TEXT,
                files TEXT DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES jobs(id),
                event TEXT NOT NULL,
                data TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """)
        self._conn.commit()

    def create_job(self, job_id: str | None = None) -> str:
        job_id = job_id or uuid.uuid4().hex[:12]
        now = time.time()
        self._conn.execute(
            "INSERT INTO jobs (id, status, created_at, updated_at) VALUES (?, 'pending', ?, ?)",
            (job_id, now, now),
        )
        self._conn.commit()
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def update_job_status(
        self,
        job_id: str,
        status: str | None = None,
        *,
        result: Any = None,
        error: str | None = None,
        files: dict[str, str] | None = None,
    ) -> None:
        now = time.time()
        fields: list[str] = ["updated_at = ?"]
        params: list[Any] = [now]
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if result is not None:
            fields.append("result = ?")
            params.append(json.dumps(result))
        if error is not None:
            fields.append("error = ?")
            params.append(error)
        if files is not None:
            current = self.get_job_files(job_id)
            current.update(files)
            fields.append("files = ?")
            params.append(json.dumps(current))
        params.append(job_id)
        self._conn.execute(
            f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        self._conn.commit()

    def get_job_files(self, job_id: str) -> dict[str, str]:
        row = self._conn.execute("SELECT files FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return {}
        raw = row["files"]
        if raw:
            return json.loads(raw)
        return {}

    def add_event(self, job_id: str, event: str, data: dict[str, Any] | None = None) -> None:
        now = time.time()
        self._conn.execute(
            "INSERT INTO job_events (job_id, event, data, created_at) VALUES (?, ?, ?, ?)",
            (job_id, event, json.dumps(data or {}), now),
        )
        self._conn.commit()

    def get_events(self, job_id: str, after_id: int = 0) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, event, data FROM job_events WHERE job_id = ? AND id > ? ORDER BY id",
            (job_id, after_id),
        ).fetchall()
        return [{"id": r["id"], "event": r["event"], "data": json.loads(r["data"])} for r in rows]

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete_old_jobs(self, max_age_hours: int = 24) -> int:
        cutoff = time.time() - max_age_hours * 3600
        deleted = self._conn.execute(
            "DELETE FROM job_events WHERE job_id IN (SELECT id FROM jobs WHERE updated_at < ?)",
            (cutoff,),
        ).rowcount
        deleted += self._conn.execute(
            "DELETE FROM jobs WHERE updated_at < ?",
            (cutoff,),
        ).rowcount
        self._conn.commit()
        return deleted

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d: dict[str, Any] = dict(row)
        if d.get("result") and isinstance(d["result"], str):
            d["result"] = json.loads(d["result"])
        if d.get("files") and isinstance(d["files"], str):
            d["files"] = json.loads(d["files"])
        return d

    def close(self) -> None:
        self._conn.close()
