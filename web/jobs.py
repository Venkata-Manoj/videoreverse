from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
from typing import Any

from src.pipeline import run_pipeline
from utils.logger import set_log_level
from web.db import Database


class JobManager:
    def __init__(self, db: Database | None = None) -> None:
        self._db = db or Database()
        self._event_queues: dict[str, queue.Queue] = {}

    def create_job(self) -> str:
        job_id = self._db.create_job()
        self._event_queues[job_id] = queue.Queue()
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self._db.get_job(job_id)

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._db.list_jobs(limit)

    def _push_event(self, job_id: str, event: str, data: dict[str, Any]) -> None:
        self._db.add_event(job_id, event, data)
        if "files" in data and isinstance(data["files"], dict):
            self._db.update_job_status(job_id, files=data["files"])
        q = self._event_queues.get(job_id)
        if q:
            q.put({"event": event, **data})

    def start_pipeline(self, job_id: str, options: dict[str, Any]) -> None:
        def on_progress(event: str, data: dict[str, Any]) -> None:
            self._push_event(job_id, event, data)

        def run() -> None:
            self._db.update_job_status(job_id, "running")
            self._push_event(job_id, "job_started", {"message": "Pipeline worker started"})
            set_log_level("warn")
            try:
                output = asyncio.run(run_pipeline(options, on_progress=on_progress))
                self._db.update_job_status(job_id, "complete", result=output)
                self._push_event(job_id, "job_complete", {"message": "Pipeline finished", "result": output})
            except Exception as err:
                self._db.update_job_status(job_id, "error", error=str(err))
                self._push_event(job_id, "pipeline_error", {"message": str(err)})
            finally:
                q = self._event_queues.get(job_id)
                if q:
                    q.put(None)

        threading.Thread(target=run, daemon=True).start()

    def start_batch(self, job_id: str, video_paths: list[str], base_options: dict[str, Any]) -> None:
        def run() -> None:
            self._db.update_job_status(job_id, "running")
            set_log_level("warn")
            total = len(video_paths)
            completed = 0
            failed = 0
            batch_results: list[dict[str, Any]] = []
            self._push_event(job_id, "batch_started", {"message": "Batch queue started", "total_files": total})

            try:
                for index, video_path in enumerate(video_paths, start=1):
                    filename = os.path.basename(video_path)
                    self._push_event(
                        job_id,
                        "batch_item",
                        {
                            "status": "running",
                            "file_index": index,
                            "total_files": total,
                            "filename": filename,
                            "message": f"Processing {filename} ({index}/{total})",
                        },
                    )

                    def make_progress(current_file: str = filename, current_index: int = index):
                        def on_progress(event: str, data: dict[str, Any]) -> None:
                            enriched = dict(data)
                            enriched["filename"] = current_file
                            enriched["file_index"] = current_index
                            enriched["total_files"] = total
                            self._push_event(job_id, event, enriched)
                        return on_progress

                    try:
                        video_options = dict(base_options)
                        video_options["video_path"] = video_path
                        output = asyncio.run(run_pipeline(video_options, on_progress=make_progress()))
                        completed += 1
                        batch_results.append({"filename": filename, "status": "complete", "output": output})
                        self._push_event(
                            job_id,
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
                        self._push_event(
                            job_id,
                            "batch_item",
                            {
                                "status": "error",
                                "file_index": index,
                                "total_files": total,
                                "filename": filename,
                                "message": f"Failed {filename}: {err}",
                            },
                        )

                result: dict[str, Any] = {
                    "mode": "batch",
                    "total_files": total,
                    "completed": completed,
                    "failed": failed,
                    "items": batch_results,
                }
                final_status = "complete" if failed == 0 else "error"
                self._db.update_job_status(job_id, final_status, result=result)
                self._push_event(
                    job_id,
                    "batch_complete",
                    {
                        "message": f"Batch finished: {completed} complete, {failed} failed",
                        "completed": completed,
                        "failed": failed,
                        "total_files": total,
                        "result": result,
                    },
                )
            except Exception as err:
                self._db.update_job_status(job_id, "error", error=str(err))
                self._push_event(job_id, "pipeline_error", {"message": str(err)})
            finally:
                q = self._event_queues.get(job_id)
                if q:
                    q.put(None)

        threading.Thread(target=run, daemon=True).start()

    def iter_events(self, job_id: str):
        job = self._db.get_job(job_id)
        if not job:
            yield f"data: {json.dumps({'event': 'error', 'message': 'Job not found'})}\n\n"
            return

        q = self._event_queues.get(job_id)
        if q is None:
            q = queue.Queue()
            self._event_queues[job_id] = q

        while True:
            item = q.get()
            if item is None:
                yield f"data: {json.dumps({'event': 'stream_end', 'status': job.get('status', 'unknown')})}\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"

    def count_jobs(self) -> int:
        return len(self._db.list_jobs(limit=99999))

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        return self._db.delete_old_jobs(max_age_hours)
