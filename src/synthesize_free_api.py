from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from typing import Any

from openai import AsyncOpenAI

from src.blueprint_prompt import BLUEPRINT_SYSTEM_PROMPT
from utils.logger import warn
from utils.retry import api_error_from_exception

MAX_FRAMES = 12
_BACKENDS_NO_RESPONSE_FORMAT = {"NVIDIA NIM"}


def _normalize_blueprint(blueprint: dict[str, Any]) -> None:
    if "chronological_shots" not in blueprint and "shots" in blueprint:
        blueprint["chronological_shots"] = blueprint.pop("shots")


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


def _build_frame_content(timeline_frames: list[dict[str, Any]], max_frames: int = MAX_FRAMES) -> list[dict[str, Any]]:
    selected = _select_frames(timeline_frames, max_frames=max_frames)
    parts: list[dict[str, Any]] = []
    for frame in selected:
        b64 = _encode_frame(frame["path"])
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            }
        )
    return parts


def _build_prompt(step1_data: dict[str, Any] | None, options: dict[str, Any]) -> str:
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

    prompt = f"""Analyze these video frames and produce a complete production blueprint in JSON.

Technical context:
- Duration: {metadata.get("duration_seconds", "unknown")}s
- Resolution: {metadata.get("dimensions", "unknown")} ({metadata.get("aspect_ratio", "unknown")})
- FPS: {metadata.get("fps", 0)}
- Codec: {metadata.get("codec", "unknown")}
- Motion level: {extraction.get("motion_signal_level", "unknown")}
- Video type: {video_type}
- Total timeline frames: {len(timeline_frames)}
- {audio_info}{transcript_str}
{audio_profile}

Break the video into chronological shots. For each shot include:
- start_time_seconds, end_time_seconds, duration_seconds
- camera_direction (static, pan, zoom, handheld, etc.)
- framing_type (wide, medium, close-up, etc.)
- action_and_motion (what happens)
- environment_context (location and background)
- negative_elements (what is NOT present)

Include a global_aesthetic with art_style, color_grading, and lighting_setup.

You MUST respond with valid JSON matching this exact structure."""
    if scene_changes:
        hints = "\n".join(
            f"- {sc.get('timestamp_seconds', 0):.2f}s: {sc.get('type', 'unknown')}" for sc in scene_changes
        )
        prompt += f"\n\nDetected cut points:\n{hints}\nUse as hints for shot segmentation."

    return prompt


async def _call_free_api(
    step1_data: dict[str, Any] | None,
    options: dict[str, Any],
    *,
    backend_name: str,
    base_url: str,
    api_key_env: str,
    model: str,
    max_frames: int = MAX_FRAMES,
) -> dict[str, Any] | None:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        warn("synthesize", f"{backend_name}: {api_key_env} not set, skipping")
        return None

    timeline_frames = step1_data.get("timeline_frames", []) if step1_data else []
    if not timeline_frames:
        raise ValueError("No timeline frames available for analysis")

    print(f"📡 {backend_name}: analyzing {min(len(timeline_frames), max_frames)} frames with {model}...", flush=True)

    user_prompt = _build_prompt(step1_data, options)
    frame_parts = _build_frame_content(timeline_frames, max_frames=max_frames)

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": BLUEPRINT_SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": user_prompt}, *frame_parts]},
        ],
        "temperature": 0.1,
    }
    if backend_name not in _BACKENDS_NO_RESPONSE_FORMAT:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await client.chat.completions.create(**kwargs)

        blueprint = json.loads(response.choices[0].message.content)
        if not blueprint.get("global_aesthetic"):
            raise ValueError("Blueprint missing global_aesthetic")
        _normalize_blueprint(blueprint)
        if not isinstance(blueprint.get("chronological_shots"), list) or len(blueprint["chronological_shots"]) == 0:
            raise ValueError("Blueprint missing chronological_shots")

        audio = step1_data.get("audio_data", {}) if step1_data else {}
        audio_mood = audio.get("mood", {})
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
            "synthesis_backend": backend_name,
            "model": model,
        }

        print(f"✅ {backend_name}: {len(blueprint['chronological_shots'])} shots identified", flush=True)
        return blueprint

    except Exception as exc:
        raise api_error_from_exception(exc) from exc


async def build_blueprint_openrouter(
    video_path: str,
    step1_data: dict[str, Any] | None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return await _call_free_api(
        step1_data,
        options or {},
        backend_name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        model="moonshotai/kimi-k2.6:free",
        max_frames=1,
    )


async def build_blueprint_nvidia(
    video_path: str,
    step1_data: dict[str, Any] | None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return await _call_free_api(
        step1_data,
        options or {},
        backend_name="NVIDIA NIM",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key_env="NVIDIA_NIM_API_KEY",
        model="nvidia/llama-3.1-nemotron-nano-vl-8b-v1",
    )
