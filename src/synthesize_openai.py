from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from typing import Any

from openai import AsyncOpenAI

from src.blueprint_prompt import BLUEPRINT_SYSTEM_PROMPT
from src.schemas.blueprint import UniversalBlueprint
from utils.retry import api_error_from_exception

MAX_FRAMES = 15


def _get_openai_client() -> AsyncOpenAI:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return AsyncOpenAI(api_key=key)


def _encode_frame(frame_path: str) -> str:
    with open(frame_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _select_frames(timeline_frames: list[dict[str, Any]], max_frames: int = MAX_FRAMES) -> list[dict[str, Any]]:
    if not timeline_frames:
        return []
    if len(timeline_frames) <= max_frames:
        return timeline_frames
    step = (len(timeline_frames) - 1) / max_frames
    selected = [timeline_frames[0]]
    for i in range(1, max_frames - 1):
        idx = int(round(i * step))
        selected.append(timeline_frames[idx])
    selected.append(timeline_frames[-1])
    return selected


def _build_frame_content(timeline_frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = _select_frames(timeline_frames)
    parts: list[dict[str, Any]] = []
    for frame in selected:
        b64 = _encode_frame(frame["path"])
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
            }
        )
    return parts


async def build_blueprint_openai(
    video_path: str,
    step1_data: dict[str, Any] | None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if options is None:
        options = {}

    print("🧠 VideoReverse: Step 3b — Blueprint Synthesis (OpenAI Fallback)", flush=True)
    print("📡 Analyzing frames with OpenAI vision...", flush=True)

    metadata = step1_data.get("video_metadata", {}) if step1_data else {}
    audio = step1_data.get("audio_data", {}) if step1_data else {}
    extraction = step1_data.get("extraction", {}) if step1_data else {}
    timeline_frames = step1_data.get("timeline_frames", []) if step1_data else []
    scene_changes = step1_data.get("scene_changes", []) if step1_data else []

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

    video_type = options.get("video_type") or "auto-detected"

    user_prompt = f"""Analyze these video frames and produce a complete production blueprint.

Technical context from local analysis:
- Duration: {metadata.get("duration_seconds", "unknown")}s
- Resolution: {metadata.get("dimensions", "unknown")} ({metadata.get("aspect_ratio", "unknown")})
- FPS: {metadata.get("fps", 0)}
- Codec: {metadata.get("codec", "unknown")}
- Motion level: {extraction.get("motion_signal_level", "unknown")}
- Video type: {video_type}
- Total timeline frames: {len(timeline_frames)}
- {audio_info}{transcript_str}
{audio_profile}

The images above are selected keyframes from the video. Analyze them and break the video into chronological shots. For each shot, describe:
1. How long it lasts (use start_time_seconds and end_time_seconds)
2. What the camera is doing (static, panning, zooming, handheld, etc.)
3. How the scene is framed (wide, close-up, etc.)
4. Exactly what happens — actions, movements, expressions, physics
5. The environment and background details
6. What is NOT present (negative elements)

For each shot, include frame_references that list which frame indices informed your analysis (index in the timeline_frames array).

Also identify the overall art style, color grading, and lighting setup.

You MUST respond with valid JSON matching the required blueprint schema."""

    if scene_changes:
        hints = "\n".join(
            f"- {sc.get('timestamp_seconds', 0):.2f}s: {sc.get('type', 'unknown')} ({sc.get('confidence', 'unknown')} confidence)"
            for sc in scene_changes
        )
        user_prompt += f"""\n\nDetected cut points from local analysis:
{hints}
Use these as hints for shot segmentation."""

    model = options.get("openai_model", "gpt-4o-mini")
    print(f"   → Using {model} with {min(len(timeline_frames), MAX_FRAMES)}/{len(timeline_frames)} frames", flush=True)

    client = _get_openai_client()
    try:
        frame_parts = _build_frame_content(timeline_frames)
        messages = [
            {"role": "system", "content": BLUEPRINT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}, *frame_parts],
            },
        ]

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        blueprint = json.loads(response.choices[0].message.content)

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
            "analysis_timestamp": datetime.now(UTC).isoformat(),
            "synthesis_backend": "openai",
            "model": model,
        }

        print("✅ Blueprint generated via OpenAI:", flush=True)
        print(f"   → {len(blueprint['chronological_shots'])} shots identified", flush=True)
        print(
            f"   → {blueprint['_metadata']['shots_with_frame_traceability']} shots with frame traceability", flush=True
        )

        return blueprint

    except Exception as exc:
        raise api_error_from_exception(exc) from exc
