from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from typing import Any

SAMPLE_MODES = ["full", "first-n", "highlights"]


def _get_video_duration(video_path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(result.stdout.strip())
        if math.isnan(duration) or duration <= 0:
            raise ValueError(f"ffprobe returned invalid duration: {result.stdout.strip()}")
        return duration
    except FileNotFoundError as err:
        raise RuntimeError("ffprobe not found. Install ffmpeg to use smart sampling.") from err
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}") from e


def _clip_first_n(video_path: str, duration_seconds: float) -> dict[str, Any]:
    temp_dir = tempfile.mkdtemp(prefix="vidrev-clip-")
    ext = os.path.splitext(video_path)[1] or ".mp4"
    clipped_path = os.path.join(temp_dir, f"clipped{ext}")

    print(f"   ✂️  Clipping first {duration_seconds}s of video...", flush=True)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-t",
                str(duration_seconds),
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                clipped_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-t", str(duration_seconds), "-y", clipped_path],
            capture_output=True,
            text=True,
            check=True,
        )

    if not os.path.exists(clipped_path) or os.path.getsize(clipped_path) == 0:
        raise RuntimeError("ffmpeg clipping failed — output file not created")

    original_size = os.path.getsize(video_path)
    clipped_size = os.path.getsize(clipped_path)
    size_reduction = (1 - clipped_size / original_size) * 100

    print(f"   → Clipped: {clipped_size / 1024 / 1024:.1f} MB ({size_reduction:.1f}% smaller)", flush=True)

    return {
        "path": clipped_path,
        "temp_dir": temp_dir,
        "mode": "first-n",
        "duration": duration_seconds,
        "size_bytes": clipped_size,
    }


def _extract_highlights(video_path: str, target_duration: float = 30) -> dict[str, Any]:
    full_duration = _get_video_duration(video_path)

    if full_duration <= target_duration:
        print(f"   → Video is {full_duration:.1f}s (≤ {target_duration}s target) — using full video", flush=True)
        return {
            "path": video_path,
            "temp_dir": None,
            "mode": "full",
            "duration": full_duration,
            "size_bytes": os.path.getsize(video_path),
        }

    temp_dir = tempfile.mkdtemp(prefix="vidrev-highlights-")
    ext = os.path.splitext(video_path)[1] or ".mp4"
    highlights_path = os.path.join(temp_dir, f"highlights{ext}")

    print(f"   🎬 Extracting {target_duration}s highlight reel from {full_duration:.1f}s video...", flush=True)
    print("   → Analyzing motion to find best segments...", flush=True)

    segment_duration = 5
    segment_count = math.ceil(target_duration / segment_duration)
    total_segments = math.ceil(full_duration / segment_duration)

    motion_scores = []
    for i in range(total_segments):
        start = i * segment_duration
        actual_duration = min(segment_duration, full_duration - start)

        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-ss",
                    str(start),
                    "-t",
                    str(actual_duration),
                    "-vf",
                    "select=gt(scene\\,0.1),metadata=print:file=/dev/stdout",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
            )
            score = result.stderr.count("lavfi")
            if score == 0:
                score = 1
            motion_scores.append({"start": start, "duration": actual_duration, "score": score})
        except Exception:
            motion_scores.append({"start": start, "duration": actual_duration, "score": 1})

    top_segments = sorted(motion_scores, key=lambda x: x["score"], reverse=True)[:segment_count]
    top_segments = sorted(top_segments, key=lambda x: x["start"])

    filter_parts = []
    concat_inputs = []
    for i, seg in enumerate(top_segments):
        filter_parts.append(f"[0:v]trim=start={seg['start']}:duration={seg['duration']},setpts=PTS-STARTPTS[v{i}]")
        concat_inputs.append(f"[v{i}]")

    filter_complex = ";".join(filter_parts) + ";" + "".join(concat_inputs) + f"concat=n={len(top_segments)}:v=1[outv]"

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-filter_complex",
                filter_complex,
                "-map",
                "[outv]",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-an",
                "-y",
                highlights_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        print("   → Motion-based extraction failed, falling back to first segment...", flush=True)
        return _clip_first_n(video_path, target_duration)

    if not os.path.exists(highlights_path) or os.path.getsize(highlights_path) == 0:
        print("   → Motion-based extraction failed, falling back to first segment...", flush=True)
        return _clip_first_n(video_path, target_duration)

    original_size = os.path.getsize(video_path)
    highlights_size = os.path.getsize(highlights_path)
    size_reduction = (1 - highlights_size / original_size) * 100

    print(f"   → Highlight reel: {highlights_size / 1024 / 1024:.1f} MB ({size_reduction:.1f}% smaller)", flush=True)
    seg_strs = [f"{s['start']:.0f}s" for s in top_segments]
    print(f"   → Top segments: {', '.join(seg_strs)}", flush=True)

    return {
        "path": highlights_path,
        "temp_dir": temp_dir,
        "mode": "highlights",
        "duration": target_duration,
        "size_bytes": highlights_size,
        "segments": top_segments,
    }


def sample_video(video_path: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    if options is None:
        options = {}

    sample_mode = options.get("sample_mode", "full")
    max_duration = options.get("max_duration")

    full_duration = _get_video_duration(video_path)
    original_size = os.path.getsize(video_path)

    print("\n── Smart Frame Sampling ──", flush=True)
    print(f"   Original: {full_duration:.1f}s, {original_size / 1024 / 1024:.1f} MB", flush=True)
    print(f"   Mode: {sample_mode}", flush=True)

    if sample_mode == "full":
        print("   → Using full video (no sampling)", flush=True)
        return {
            "path": video_path,
            "temp_dir": None,
            "mode": "full",
            "duration": full_duration,
            "size_bytes": original_size,
            "original_duration": full_duration,
        }

    if sample_mode == "first-n":
        clip_duration = max_duration if max_duration else 30
        if clip_duration >= full_duration:
            print(
                f"   → Requested {clip_duration}s ≥ video duration {full_duration:.1f}s — using full video", flush=True
            )
            return {
                "path": video_path,
                "temp_dir": None,
                "mode": "full",
                "duration": full_duration,
                "size_bytes": original_size,
                "original_duration": full_duration,
            }
        return _clip_first_n(video_path, clip_duration)

    if sample_mode == "highlights":
        target_duration = max_duration if max_duration else 30
        return _extract_highlights(video_path, target_duration)

    raise ValueError(f"Unknown sample mode: {sample_mode}. Use: {', '.join(SAMPLE_MODES)}")


def cleanup_sample(sample_result: dict[str, Any] | None) -> None:
    if sample_result and sample_result.get("temp_dir") and os.path.exists(sample_result["temp_dir"]):
        try:
            shutil.rmtree(sample_result["temp_dir"], ignore_errors=True)
            print("   → Cleaned up temporary sample files", flush=True)
        except Exception as e:
            print(f"   → Cleanup warning: {e}", flush=True)
