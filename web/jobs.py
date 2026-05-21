from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.pipeline import run_pipeline
from utils.logger import set_log_level


@dataclass
class Job:
    id: str
    status: str = "pending"
    events: queue.Queue = field(default_factory=queue.Queue)
    result: dict[str, Any] | None = None
    error: str | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _push(self, job: Job, event: str, data: dict[str, Any]) -> None:
        payload = {"event": event, **data}
        job.events.put(payload)

    def start(self, job: Job, options: dict[str, Any]) -> None:
        def on_progress(event: str, data: dict[str, Any]) -> None:
            self._push(job, event, data)

        def run() -> None:
            job.status = "running"
            self._push(job, "job_started", {"message": "Pipeline worker started"})
            set_log_level("warn")
            try:
                output = asyncio.run(run_pipeline(options, on_progress=on_progress))
                job.result = output
                job.status = "complete"
            except Exception as err:
                job.error = str(err)
                job.status = "error"
            finally:
                job.events.put(None)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def iter_events(self, job_id: str):
        job = self.get(job_id)
        if not job:
            yield f"data: {json.dumps({'event': 'error', 'message': 'Job not found'})}\n\n"
            return

        while True:
            item = job.events.get()
            if item is None:
                yield f"data: {json.dumps({'event': 'stream_end', 'status': job.status})}\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"
