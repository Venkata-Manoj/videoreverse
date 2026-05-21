"""Multi-video batch processing with parallel execution and resume support."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.pipeline import run_pipeline
from utils.logger import error, info, warn

BATCH_STATE_FILE = "batch_state.json"


def load_video_list(batch_source: str) -> list[str]:
    batch_path = Path(batch_source)
    if batch_path.is_dir():
        video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
        videos = []
        for f in sorted(batch_path.iterdir()):
            if f.suffix.lower() in video_extensions:
                videos.append(str(f))
        return videos
    if batch_path.is_file():
        with open(batch_path, encoding="utf-8") as f:
            lines = f.readlines()
        return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    return [batch_source]


def load_batch_state(output_dir: str) -> dict[str, Any]:
    state_path = Path(output_dir) / BATCH_STATE_FILE
    if state_path.exists():
        with open(state_path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_at": None,
        "videos": {},
        "completed": [],
        "failed": [],
        "skipped": [],
    }


def save_batch_state(state: dict[str, Any], output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    state_path = Path(output_dir) / BATCH_STATE_FILE
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def is_video_completed(video_path: str, state: dict[str, Any]) -> bool:
    normalized = os.path.abspath(video_path)
    return normalized in state.get("completed", [])


async def process_single_video(
    video_path: str,
    base_options: dict[str, Any],
    semaphore: asyncio.Semaphore,
    state: dict[str, Any],
    output_dir: str,
) -> dict[str, Any]:
    async with semaphore:
        normalized = os.path.abspath(video_path)
        video_name = Path(video_path).stem
        start_time = time.time()
        info("batch", f"Processing: {video_name}")
        state["videos"][normalized] = {
            "path": video_path,
            "status": "running",
            "started_at": datetime.now(UTC).isoformat(),
        }
        save_batch_state(state, output_dir)
        try:
            video_options = dict(base_options)
            video_options["video_path"] = video_path
            result = await run_pipeline(video_options)
            elapsed = time.time() - start_time
            state["videos"][normalized]["status"] = "completed"
            state["videos"][normalized]["elapsed_seconds"] = round(elapsed, 2)
            state["videos"][normalized]["completed_at"] = datetime.now(UTC).isoformat()
            if normalized not in state["completed"]:
                state["completed"].append(normalized)
            save_batch_state(state, output_dir)
            info("batch", f"Completed: {video_name} ({elapsed:.1f}s)")
            return {"video": video_path, "status": "success", "elapsed": elapsed, "result": result}
        except Exception as e:
            elapsed = time.time() - start_time
            state["videos"][normalized]["status"] = "failed"
            state["videos"][normalized]["error"] = str(e)
            state["videos"][normalized]["elapsed_seconds"] = round(elapsed, 2)
            state["videos"][normalized]["failed_at"] = datetime.now(UTC).isoformat()
            if normalized not in state["failed"]:
                state["failed"].append(normalized)
            save_batch_state(state, output_dir)
            error("batch", f"Failed: {video_name} — {e}")
            return {"video": video_path, "status": "failed", "elapsed": elapsed, "error": str(e)}


async def run_batch_pipeline(
    batch_source: str,
    base_options: dict[str, Any],
    max_parallel: int = 4,
) -> dict[str, Any]:
    batch_start = time.time()
    output_dir = base_options.get("output_dir", "output_blueprints")
    video_list = load_video_list(batch_source)
    if not video_list:
        raise ValueError(f"No videos found in: {batch_source}")
    print("\n" + "=" * 60, flush=True)
    print("  VideoReverse — Batch Processing", flush=True)
    print("=" * 60, flush=True)
    print(f"  Videos: {len(video_list)}", flush=True)
    print(f"  Parallel: {max_parallel}", flush=True)
    print(f"  Gemini model: {base_options.get('gemini_model', 'gemini-2.5-flash')}", flush=True)
    print("=" * 60 + "\n", flush=True)
    state = load_batch_state(output_dir)
    if state["started_at"] is None:
        state["started_at"] = datetime.now(UTC).isoformat()
        save_batch_state(state, output_dir)
    pending_videos = [v for v in video_list if not is_video_completed(v, state)]
    skipped_videos = [v for v in video_list if is_video_completed(v, state)]
    for v in skipped_videos:
        normalized = os.path.abspath(v)
        if normalized not in state.get("skipped", []):
            state.setdefault("skipped", []).append(normalized)
    if skipped_videos:
        print(f"  ⏭️  Skipping {len(skipped_videos)} completed video(s) (resume mode)", flush=True)
    if not pending_videos:
        print("  All videos already completed.", flush=True)
        save_batch_state(state, output_dir)
        return generate_batch_summary(state, batch_start)
    print(f"  Processing {len(pending_videos)} video(s)...\n", flush=True)
    semaphore = asyncio.Semaphore(max_parallel)
    tasks = []
    for video_path in pending_videos:
        task = asyncio.create_task(
            process_single_video(video_path, base_options, semaphore, state, output_dir)
        )
        tasks.append(task)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            video_path = pending_videos[i]
            normalized = os.path.abspath(video_path)
            state["videos"][normalized] = {
                "path": video_path,
                "status": "failed",
                "error": str(result),
                "failed_at": datetime.now(UTC).isoformat(),
            }
            if normalized not in state["failed"]:
                state["failed"].append(normalized)
    save_batch_state(state, output_dir)
    return generate_batch_summary(state, batch_start)


def generate_batch_summary(state: dict[str, Any], batch_start: float) -> dict[str, Any]:
    total_elapsed = time.time() - batch_start
    completed_count = len(state.get("completed", []))
    failed_count = len(state.get("failed", []))
    skipped_count = len(state.get("skipped", []))
    total_count = completed_count + failed_count + skipped_count
    summary = {
        "batch_started_at": state["started_at"],
        "completed_at": datetime.now(UTC).isoformat(),
        "total_elapsed_seconds": round(total_elapsed, 2),
        "total_videos": total_count,
        "completed": completed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "success_rate": round(completed_count / total_count * 100, 1) if total_count > 0 else 0,
        "videos": state.get("videos", {}),
    }
    print("\n" + "=" * 60, flush=True)
    print("  Batch Processing Summary", flush=True)
    print("=" * 60, flush=True)
    print(f"  Total videos:  {total_count}", flush=True)
    print(f"  Completed:     {completed_count} ✓", flush=True)
    print(f"  Failed:        {failed_count} ✗", flush=True)
    print(f"  Skipped:       {skipped_count} (resume)", flush=True)
    print(f"  Success rate:  {summary['success_rate']:.1f}%", flush=True)
    print(f"  Total time:    {total_elapsed:.1f}s", flush=True)
    if failed_count > 0:
        print(f"\n  Failed videos:", flush=True)
        for normalized_path in state.get("failed", []):
            video_info = state["videos"].get(normalized_path, {})
            err = video_info.get("error", "unknown")
            print(f"    - {Path(normalized_path).stem}: {err}", flush=True)
    print("\n" + "=" * 60 + "\n", flush=True)
    return summary
