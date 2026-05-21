#!/usr/bin/env python3
"""Prompt Quality Benchmark — compares current blueprint output against reference outputs."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark.metrics import calculate_overall_quality

BENCHMARK_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = BENCHMARK_DIR / "references"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "test_results"
QUALITY_HISTORY = RESULTS_DIR / "quality_history.json"


def load_reference(video_name: str) -> dict[str, Any] | None:
    ref_path = REFERENCE_DIR / f"{video_name}.json"
    if not ref_path.exists():
        return None
    with open(ref_path, encoding="utf-8") as f:
        return json.load(f)


def load_blueprint(output_dir: str, video_name: str) -> dict[str, Any] | None:
    output_path = Path(output_dir)
    if not output_path.exists():
        return None
    for f in sorted(output_path.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix == ".json" and video_name in f.stem:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
                return data.get("blueprint", data)
    return None


def save_quality_result(result: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history = []
    if QUALITY_HISTORY.exists():
        with open(QUALITY_HISTORY, encoding="utf-8") as f:
            try:
                history = json.load(f)
            except (json.JSONDecodeError, Exception):
                history = []
    history.append(result)
    with open(QUALITY_HISTORY, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def run_benchmark_for_video(
    video_name: str,
    output_dir: str = "output_blueprints",
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if reference is None:
        reference = load_reference(video_name)
    if reference is None:
        return {
            "video": video_name,
            "status": "skipped",
            "reason": "No reference blueprint found",
        }
    blueprint = load_blueprint(output_dir, video_name)
    if blueprint is None:
        return {
            "video": video_name,
            "status": "skipped",
            "reason": "No current blueprint found in output directory",
        }
    quality = calculate_overall_quality(blueprint, reference)
    return {
        "video": video_name,
        "status": "completed",
        "timestamp": datetime.now(UTC).isoformat(),
        "quality": quality,
    }


def create_reference(video_name: str, blueprint: dict[str, Any]) -> str:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    ref_path = REFERENCE_DIR / f"{video_name}.json"
    with open(ref_path, "w", encoding="utf-8") as f:
        json.dump(blueprint, f, indent=2)
    return str(ref_path)


def print_benchmark_report(results: list[dict[str, Any]]) -> None:
    print("\n" + "=" * 60, flush=True)
    print("  Prompt Quality Benchmark Report", flush=True)
    print("=" * 60, flush=True)
    completed = [r for r in results if r.get("status") == "completed"]
    skipped = [r for r in results if r.get("status") == "skipped"]
    for r in completed:
        q = r["quality"]
        grade = q["grade"]
        score = q["overall_score"]
        print(f"\n  [{grade}] {r['video']} — Score: {score:.2%}", flush=True)
        for metric_name, metric_val in q["metrics"].items():
            bar = "█" * int(metric_val * 10) + "░" * (10 - int(metric_val * 10))
            print(f"      {metric_name:30s} [{bar}] {metric_val:.2%}", flush=True)
    if skipped:
        print(f"\n  Skipped ({len(skipped)}):", flush=True)
        for r in skipped:
            print(f"    - {r['video']}: {r.get('reason', 'unknown')}", flush=True)
    if completed:
        avg_score = sum(r["quality"]["overall_score"] for r in completed) / len(completed)
        print(f"\n  Average Quality Score: {avg_score:.2%}", flush=True)
    print("\n" + "=" * 60 + "\n", flush=True)


def main() -> None:
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(
            """
Usage: python -m benchmark [options]

Options:
  --video <name>       Benchmark specific video (default: all test videos)
  --output-dir <dir>   Directory with generated blueprints (default: output_blueprints)
  --create-reference   Create reference from current output instead of benchmarking
  --video-name <name>  Video name for --create-reference mode
  --help, -h           Show this help message

Test videos: test1, test_drone, test_anime, test_vlog
""",
            flush=True,
        )
        sys.exit(0)
    output_dir = "output_blueprints"
    create_ref = False
    specific_video = None
    ref_video_name = None
    i = 0
    while i < len(args):
        if args[i] == "--video" and i + 1 < len(args):
            i += 1
            specific_video = args[i]
        elif args[i] == "--output-dir" and i + 1 < len(args):
            i += 1
            output_dir = args[i]
        elif args[i] == "--create-reference":
            create_ref = True
        elif args[i] == "--video-name" and i + 1 < len(args):
            i += 1
            ref_video_name = args[i]
        i += 1
    if create_ref:
        if ref_video_name is None:
            print("Error: --video-name required with --create-reference", file=sys.stderr)
            sys.exit(1)
        blueprint = load_blueprint(output_dir, ref_video_name)
        if blueprint is None:
            print(f"Error: No blueprint found for '{ref_video_name}' in {output_dir}", file=sys.stderr)
            sys.exit(1)
        path = create_reference(ref_video_name, blueprint)
        print(f"Reference created: {path}", flush=True)
        sys.exit(0)
    test_videos = ["test1", "test_drone", "test_anime", "test_vlog"]
    if specific_video:
        test_videos = [specific_video]
    print(f"Running benchmark for {len(test_videos)} video(s)...", flush=True)
    results = []
    start = time.time()
    for vid in test_videos:
        result = run_benchmark_for_video(vid, output_dir)
        results.append(result)
        if result["status"] == "completed":
            save_quality_result(result)
    elapsed = time.time() - start
    print(f"Benchmark completed in {elapsed:.2f}s", flush=True)
    print_benchmark_report(results)
    completed = [r for r in results if r.get("status") == "completed"]
    if completed:
        avg = sum(r["quality"]["overall_score"] for r in completed) / len(completed)
        if avg < 0.6:
            print("⚠️  Quality below threshold (60%). Review blueprints.", flush=True)
            sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
