from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google import genai

from src.blueprint_prompt import BLUEPRINT_SCHEMA, BLUEPRINT_SYSTEM_PROMPT
from src.path_resolver import get_root


def _load_env_key() -> str | None:
    env_path = os.path.join(get_root(), ".env")
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                trimmed = line.strip()
                if not trimmed or trimmed.startswith("#"):
                    continue
                eq = trimmed.find("=")
                if eq == -1:
                    continue
                key = trimmed[:eq].strip()
                val = trimmed[eq + 1 :].strip()
                if key == "GEMINI_API_KEY":
                    return val
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


_api_key = _load_env_key()
if not _api_key:
    raise RuntimeError("GEMINI_API_KEY not found in .env or environment")

_client = genai.Client(api_key=_api_key)


def _build_frame_context(timeline_frames: list[dict[str, Any]]) -> str:
    if not timeline_frames or len(timeline_frames) == 0:
        return "- Frames extracted: 0"

    lines = ["- Frame timeline (ffmpeg extracted keyframes):"]
    lines.append(f"  Total frames: {len(timeline_frames)}")

    high_motion_frames = [f for f in timeline_frames if f.get("motion_level") == "high"]
    low_motion_frames = [f for f in timeline_frames if f.get("motion_level") == "low"]

    if high_motion_frames:
        indices = ", ".join(str(f["index"]) for f in high_motion_frames[:5])
        more = f" (+{len(high_motion_frames) - 5} more)" if len(high_motion_frames) > 5 else ""
        lines.append(f"  High motion frames: [{indices}]{more}")

    if low_motion_frames:
        indices = ", ".join(str(f["index"]) for f in low_motion_frames[:5])
        more = f" (+{len(low_motion_frames) - 5} more)" if len(low_motion_frames) > 5 else ""
        lines.append(f"  Low motion frames: [{indices}]{more}")

    motion_transitions = _detect_motion_transitions(timeline_frames)
    if motion_transitions:
        ts_strs = [f"{t['timestamp']:.1f}s" for t in motion_transitions]
        lines.append(f"  Motion transitions (likely cut points): {', '.join(ts_strs)}")

    frame_groups = _group_frames_by_motion(timeline_frames)
    if len(frame_groups) > 1:
        lines.append(f"  Frame groups (by motion similarity): {len(frame_groups)} groups")
        for group in frame_groups[:5]:
            lines.append(
                f"    Group {group['id']}: frames [{', '.join(str(i) for i in group['frame_indices'])}] "
                f"@ {group['start_timestamp']:.1f}s-{group['end_timestamp']:.1f}s ({group['motion_level']} motion)"
            )

    lines.append("")
    lines.append("  Frame details (format: [index] @timestamp_s - motion):")

    for frame in timeline_frames[:20]:
        ts = f"{frame.get('timestamp_seconds', 0):.2f}"
        motion = frame.get("motion_level", "medium")
        lines.append(f"    [{frame['index']}] @ {ts}s - {motion}")

    if len(timeline_frames) > 20:
        lines.append(f"    ... and {len(timeline_frames) - 20} more frames")

    return "\n".join(lines)


def _detect_motion_transitions(timeline_frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(timeline_frames) < 3:
        return []

    transitions = []
    for i in range(1, len(timeline_frames) - 1):
        prev = timeline_frames[i - 1]
        curr = timeline_frames[i]
        next_frame = timeline_frames[i + 1]

        def motion_value(f):
            ml = f.get("motion_level", "medium")
            return 2 if ml == "high" else (0 if ml == "low" else 1)

        prev_m = motion_value(prev)
        curr_m = motion_value(curr)
        next_m = motion_value(next_frame)

        if abs(curr_m - prev_m) >= 2 or abs(next_m - curr_m) >= 2:
            transitions.append(
                {
                    "frame_index": i,
                    "timestamp": curr.get("timestamp_seconds", 0),
                    "type": "motion_shift",
                }
            )

    return transitions


def _group_frames_by_motion(timeline_frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not timeline_frames:
        return []

    groups = []
    current_group = {
        "id": 0,
        "frame_indices": [timeline_frames[0]["index"]],
        "motion_level": timeline_frames[0].get("motion_level", "medium"),
        "start_timestamp": timeline_frames[0].get("timestamp_seconds", 0),
        "end_timestamp": timeline_frames[0].get("timestamp_seconds", 0),
    }

    for i in range(1, len(timeline_frames)):
        frame = timeline_frames[i]
        motion = frame.get("motion_level", "medium")

        if motion == current_group["motion_level"]:
            current_group["frame_indices"].append(frame["index"])
            current_group["end_timestamp"] = frame.get("timestamp_seconds", 0)
        else:
            groups.append(dict(current_group))
            current_group = {
                "id": len(groups),
                "frame_indices": [frame["index"]],
                "motion_level": motion,
                "start_timestamp": frame.get("timestamp_seconds", 0),
                "end_timestamp": frame.get("timestamp_seconds", 0),
            }

    if current_group["frame_indices"]:
        groups.append(current_group)

    return groups


def _build_shot_boundary_hints(scene_changes: list[dict[str, Any]] | None) -> str | None:
    if not scene_changes or len(scene_changes) == 0:
        return None

    hints = "\n".join(
        f"- {sc.get('timestamp_seconds', 0):.2f}s: {sc.get('type', 'unknown')} ({sc.get('confidence', 'unknown')} confidence)"
        for sc in scene_changes
    )

    return f"Detected {len(scene_changes)} potential cut points:\n{hints}"


def _extract_motion_transitions(timeline_frames: list[dict[str, Any]] | None) -> str | None:
    if not timeline_frames or len(timeline_frames) < 3:
        return None

    transitions = []
    for i in range(1, len(timeline_frames) - 1):
        prev = timeline_frames[i - 1]
        curr = timeline_frames[i]
        next_frame = timeline_frames[i + 1]

        def motion_value(f):
            ml = f.get("motion_level", "medium")
            return 2 if ml == "high" else (0 if ml == "low" else 1)

        prev_m = motion_value(prev)
        curr_m = motion_value(curr)
        next_m = motion_value(next_frame)

        if abs(curr_m - prev_m) >= 2 or abs(next_m - curr_m) >= 2:
            transitions.append(f"{curr.get('timestamp_seconds', 0):.1f}s (frame {curr['index']})")

    return ", ".join(transitions) if transitions else None


async def build_blueprint(
    video_path: str,
    step1_data: dict[str, Any] | None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if options is None:
        options = {}

    print("🧠 VideoReverse: Step 3 — Blueprint Synthesis (Frame-Aware)", flush=True)
    print("📡 Uploading video to Gemini File API...", flush=True)

    normalized = video_path
    if not os.path.exists(normalized):
        raise FileNotFoundError(f"Video file not found: {normalized}")

    uploaded_file = None
    try:
        uploaded_file = await _client.aio.files.upload(
            file=normalized,
            config={"mime_type": "video/mp4"},
        )
        size_mb = uploaded_file.size_bytes / 1024 / 1024 if hasattr(uploaded_file, "size_bytes") else 0
        print(f"   → Uploaded: {uploaded_file.name} ({size_mb:.1f} MB)", flush=True)

        print("   → Waiting for file processing...", flush=True)
        processing = False
        for i in range(60):
            import asyncio

            await asyncio.sleep(1)
            status = await _client.aio.files.get(name=uploaded_file.name)
            if status.state == "ACTIVE":
                print(f"   → File ready ({i + 1}s)", flush=True)
                processing = True
                break
            if status.state == "FAILED":
                error_msg = getattr(status, "error", None)
                error_message = getattr(error_msg, "message", "unknown error") if error_msg else "unknown error"
                raise RuntimeError(f"File processing failed: {error_message}")
        if not processing:
            raise RuntimeError("File processing timed out after 60s")

        metadata = step1_data.get("video_metadata", {}) if step1_data else {}
        audio = step1_data.get("audio_data", {}) if step1_data else {}
        extraction = step1_data.get("extraction", {}) if step1_data else {}
        timeline_frames = step1_data.get("timeline_frames", []) if step1_data else []
        scene_changes = step1_data.get("scene_changes", []) if step1_data else []

        frame_context = _build_frame_context(timeline_frames)
        shot_boundary_hints = _build_shot_boundary_hints(scene_changes)
        motion_transitions = _extract_motion_transitions(timeline_frames)

        audio_mood = audio.get("mood", {})
        audio_info = (
            f"Audio mood: {audio_mood['mood']}"
            if audio_mood and audio_mood.get("mood")
            else f"Audio: {'Yes' if audio.get('has_audio') else 'No'}"
        )

        transcript = audio.get("transcript", "")
        transcript_str = f' — Transcript: "{transcript}"' if transcript else ""

        audio_profile = ""
        if audio_mood and audio_mood.get("indicators"):
            indicators = [k for k, v in audio_mood["indicators"].items() if v]
            audio_profile = f" - Audio profile: {', '.join(indicators) if indicators else 'none'}"

        user_prompt = f"""Analyze this video and produce a complete production blueprint with frame-aware analysis.

Technical context from local analysis:
- Duration: {metadata.get("duration_seconds", "unknown")}s
- Resolution: {metadata.get("dimensions", "unknown")} ({metadata.get("aspect_ratio", "unknown")})
- FPS: {metadata.get("fps", 0)}
- Codec: {metadata.get("codec", "unknown")}
- Motion level: {extraction.get("motion_signal_level", "unknown")}
{frame_context}
- {audio_info}{transcript_str}
{audio_profile}

Break the video into chronological shots. For each shot, describe:
1. How long it lasts (use start_time_seconds and end_time_seconds)
2. What the camera is doing (static, panning, zooming, handheld, etc.)
3. How the scene is framed (wide, close-up, etc.)
4. Exactly what happens — actions, movements, expressions, physics
5. The environment and background details
6. What is NOT present (negative elements)

CRITICAL - Frame Reference Requirements:
For EACH shot, you MUST include a frame_references array that:
- Lists which timeline frames (by index) informed this shot
- Correlates shot times with frame timestamps
- Indicates frame relevance (key_frame, transition_frame, supporting)
- Shows which frames triggered the shot boundary

Also identify the overall art style, color grading, and lighting setup.
"""

        if shot_boundary_hints:
            user_prompt += f"""
CRITICAL - Shot Boundary Hints:
The following timestamps were identified as likely shot boundaries from local frame analysis:
{shot_boundary_hints}
Use these timestamps as hints to guide your shot segmentation. Validate against actual scene changes in the video."""

        if motion_transitions:
            user_prompt += f"""
Motion Transition Analysis:
The following timestamps show significant motion level changes (likely cut points):
{motion_transitions}
Use these as additional hints for shot boundary detection."""

        system_instruction = BLUEPRINT_SYSTEM_PROMPT

        if audio_mood and audio_mood.get("mood"):
            system_instruction += f'\n\nAudio mood context: "{audio_mood["mood"]}". '
            if audio_mood["mood"] == "dynamic":
                system_instruction += "Expect high-energy content with music and action."
            elif audio_mood["mood"] == "contemplative":
                system_instruction += "Expect slow-paced content with ambient sound."
            elif audio_mood["mood"] == "documentary":
                system_instruction += "Expect speech-heavy content with dialogue."

        if extraction.get("motion_signal_level") == "high":
            system_instruction += " High motion content - emphasize dynamic camera work."
        elif extraction.get("motion_signal_level") == "low":
            system_instruction += " Low motion content - emphasize static compositions."

        system_instruction += f"\n\nFrame-aware analysis enabled. Total frames in timeline: {len(timeline_frames)}.\nEach shot MUST include frame_references correlating to the timeline."

        gemini_model = options.get("gemini_model", "gemini-2.5-flash")
        print(f"🔍 Sending to Gemini ({gemini_model}) for frame-aware multimodal analysis...", flush=True)
        print(f"   → Frame context: {len(timeline_frames)} frames available", flush=True)
        if scene_changes:
            print(f"   → Shot boundary hints: {len(scene_changes)} potential cut points detected", flush=True)
        if motion_transitions:
            print(
                f"   → Motion transitions: {len(motion_transitions.split(', ')) if isinstance(motion_transitions, str) else 0} likely cut points from frame analysis",
                flush=True,
            )

        from google.genai import types

        response = await _client.aio.models.generate_content(
            model=gemini_model,
            contents=[
                user_prompt,
                types.FileData(file_uri=uploaded_file.uri, mime_type="video/mp4"),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BLUEPRINT_SCHEMA,
                system_instruction=system_instruction,
            ),
        )

        blueprint = json.loads(response.text)

        if not blueprint.get("global_aesthetic") or not isinstance(blueprint.get("chronological_shots"), list):
            raise ValueError("Blueprint missing required fields")

        if audio_mood and audio_mood.get("mood"):
            blueprint["global_aesthetic"]["_audio_mood"] = audio_mood["mood"]

        blueprint["_metadata"] = {
            "total_frames_analyzed": len(timeline_frames),
            "shots_with_frame_traceability": len(
                [
                    s
                    for s in blueprint["chronological_shots"]
                    if s.get("frame_references") and len(s["frame_references"]) > 0
                ]
            ),
            "analysis_timestamp": None,
            "frame_timeline": [
                {
                    "index": f["index"],
                    "timestamp_seconds": f.get("timestamp_seconds", 0),
                    "motion_level": f.get("motion_level", "medium"),
                }
                for f in timeline_frames
            ],
            "detected_scene_changes": [
                {
                    "index": sc.get("index", 0),
                    "timestamp_seconds": sc.get("timestamp_seconds", 0),
                    "type": sc.get("type", "unknown"),
                    "confidence": sc.get("confidence", "unknown"),
                }
                for sc in scene_changes
            ],
        }

        from datetime import datetime, timezone

        blueprint["_metadata"]["analysis_timestamp"] = datetime.now(UTC).isoformat()

        print("✅ Frame-aware blueprint generated:", flush=True)
        print(f"   → {len(blueprint['chronological_shots'])} shots identified", flush=True)
        print(
            f"   → {blueprint['_metadata']['shots_with_frame_traceability']} shots with frame traceability", flush=True
        )

        if scene_changes:
            shot_count = len(blueprint["chronological_shots"])
            expected_shots = len(scene_changes) + 1
            variance = abs(shot_count - expected_shots)
            if variance > 2:
                print(
                    f"   ⚠️ Shot count mismatch: expected ~{expected_shots} shots based on {len(scene_changes)} detected cut points, got {shot_count}",
                    flush=True,
                )
                blueprint["_metadata"]["shot_count_warning"] = {
                    "expected_based_on_scene_changes": expected_shots,
                    "actual_shots": shot_count,
                    "variance": variance,
                    "message": "Gemini shot count differs significantly from local scene detection - verify accuracy",
                }

        return blueprint

    finally:
        if uploaded_file:
            try:
                await _client.aio.files.delete(name=uploaded_file.name)
                print("   → Cleaned up uploaded file from Gemini", flush=True)
            except Exception as e:
                print(f"   → Cleanup warning: {e}", flush=True)
