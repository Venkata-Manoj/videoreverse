from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask

from web.app import app, job_manager
from web.db import Database


@pytest.fixture
def client() -> Flask.test_client:
    db_path = tempfile.mktemp(suffix=".db")
    db = Database(db_path)
    with patch("web.app.job_manager") as mock_mgr:
        mock_mgr._db = db
        mock_mgr.create_job.return_value = "test-job-001"

        def _get_job(job_id: str) -> dict | None:
            if job_id == "test-job-001":
                return {
                    "id": "test-job-001",
                    "status": "complete",
                    "result": {"blueprint": {"global_aesthetic": {"art_style": "test"}}},
                    "files": {"json": "/tmp/test.json"},
                }
            return None

        mock_mgr.get_job.side_effect = _get_job
        mock_mgr.count_jobs.return_value = 3
        mock_mgr.iter_events.return_value = iter([])
        with app.test_client() as c:
            yield c
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_health_endpoint(client: Flask.test_client) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True


def test_config_endpoint(client: Flask.test_client) -> None:
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "models" in data
    assert "sample_modes" in data


def test_monitoring_endpoint(client: Flask.test_client) -> None:
    resp = client.get("/api/monitoring")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "hub_jobs" in data


def test_get_job_endpoint(client: Flask.test_client) -> None:
    resp = client.get("/api/jobs/test-job-001")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["id"] == "test-job-001"
    assert data["status"] == "complete"


def test_get_nonexistent_job(client: Flask.test_client) -> None:
    resp = client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404


def test_templates_endpoint(client: Flask.test_client) -> None:
    resp = client.get("/api/templates")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "templates" in data
    assert "models" in data
    assert len(data["models"]) > 0
