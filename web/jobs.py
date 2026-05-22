from __future__ import annotations

import asyncio
import json
import os
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
    files: dict[str, str] = field(default_factory=dict)


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
        if "files" in data and isinstance(data["files"], dict):
            job.files.update(data["files"])
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

    def start_batch(self, job: Job, video_paths: list[str], base_options: dict[str, Any]) -> None:
        def run() -> None:
            job.status = "running"
            set_log_level("warn")
            total = len(video_paths)
            completed = 0
            failed = 0
            batch_results: list[dict[str, Any]] = []
            self._push(job, "batch_started", {"message": "Batch queue started", "total_files": total})

            try:
                for index, video_path in enumerate(video_paths, start=1):
                    filename = os.path.basename(video_path)
                    self._push(
                        job,
                        "batch_item",
                        {
                            "status": "running",
                            "file_index": index,
                            "total_files": total,
                            "filename": filename,
                            "message": f"Processing {filename} ({index}/{total})",
                        },
                    )

                    def on_progress(event: str, data: dict[str, Any], *, current_file: str = filename, current_index: int = index) -> None:
                        enriched = dict(data)
                        enriched["filename"] = current_file
                        enriched["file_index"] = current_index
                        enriched["total_files"] = total
                        self._push(job, event, enriched)

                    try:
                        video_options = dict(base_options)
                        video_options["video_path"] = video_path
                        output = asyncio.run(run_pipeline(video_options, on_progress=on_progress))
                        completed += 1
                        batch_results.append({"filename": filename, "status": "complete", "output": output})
                        self._push(
                            job,
                            "batch_item",
                            {
                                "status": "complete",
                                "file_index": index,
                                "total_files": total,
                                "filename": filename,
                                "message": f"Completed {filename}",
                            },
                        )
                    except Exception as err:
                        failed += 1
                        batch_results.append({"filename": filename, "status": "error", "error": str(err)})
                        self._push(
                            job,
                            "batch_item",
                            {
                                "status": "error",
                                "file_index": index,
                                "total_files": total,
                                "filename": filename,
                                "message": f"Failed {filename}: {err}",
                            },
                        )

                job.result = {
                    "mode": "batch",
                    "total_files": total,
                    "completed": completed,
                    "failed": failed,
                    "items": batch_results,
                }
                job.status = "complete" if failed == 0 else "error"
                self._push(
                    job,
                    "batch_complete",
                    {
                        "message": f"Batch finished: {completed} complete, {failed} failed",
                        "completed": completed,
                        "failed": failed,
                        "total_files": total,
                        "result": job.result,
                    },
                )
            except Exception as err:
                job.error = str(err)
                job.status = "error"
                self._push(job, "pipeline_error", {"message": str(err)})
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
