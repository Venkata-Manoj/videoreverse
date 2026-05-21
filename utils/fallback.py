from __future__ import annotations

from typing import Any

from src.compile import compile_prompts


class FallbackMode:
    def __init__(self) -> None:
        self.enabled = False
        self.reason: str | None = None

    def activate(self, reason: str) -> None:
        self.enabled = True
        self.reason = reason

    def is_active(self) -> bool:
        return self.enabled

    def get_reason(self) -> str | None:
        return self.reason


def build_fallback_blueprint(step1_data: dict[str, Any] | None) -> dict[str, Any]:
    metadata = step1_data.get("video_metadata", {}) if step1_data else {}
    audio = step1_data.get("audio_data", {}) if step1_data else {}
    extraction = step1_data.get("extraction", {}) if step1_data else {}

    duration = metadata.get("duration_seconds", 10)
    aspect_ratio = metadata.get("aspect_ratio", "16:9")
    fps = metadata.get("fps", 30)

    style = "cinematic"
    if fps < 24:
        style = "low-fi recording"
    if extraction.get("motion_signal_level") == "high":
        style = "dynamic action"
    if extraction.get("motion_signal_level") == "low":
        style = "static scene"

    color_grade = "natural color"
    if audio.get("transcript") and len(audio.get("transcript", "")) > 100:
        color_grade = "documentary style"

    lighting = "natural lighting"
    dims = metadata.get("width") and metadata.get("height")
    if dims:
        brightness = (metadata["width"] * metadata["height"]) / (1920 * 1080)
        if brightness > 1.2:
            lighting = "bright ambient lighting"
        if brightness < 0.8:
            lighting = "low-key moody lighting"

    shot_count = max(1, int(duration / 5 + 0.999))  # ceil equivalent

    shots = []
    for i in range(shot_count):
        shot_duration = min(5, duration - (i * 5))
        if shot_duration <= 0:
            break

        shots.append(
            {
                "shot_index": i,
                "duration_seconds": shot_duration,
                "camera_direction": "static establishing shot" if i == 0 else "medium shot",
                "framing_type": "wide shot" if i == 0 else "medium shot",
                "action_and_motion": (
                    f'Dialogue: "{audio.get("transcript", "")[:100]}..."'
                    if audio.get("transcript")
                    else f"Scene content based on {fps}fps motion analysis"
                ),
                "environment_context": f"Video dimensions: {metadata.get('dimensions', 'unknown')}, codec: {metadata.get('codec', 'unknown')}",
                "negative_elements": [
                    "artifacts",
                    "compression noise",
                    "wrong aspect ratio",
                ],
            }
        )

    return {
        "global_aesthetic": {
            "art_style": style,
            "color_grading": color_grade,
            "lighting_setup": lighting,
        },
        "chronological_shots": shots,
        "_fallback_metadata": {
            "source": "text-only-fallback",
            "reason": "Gemini analysis unavailable",
            "based_on": {
                "duration_seconds": duration,
                "dimensions": metadata.get("dimensions"),
                "fps": fps,
                "codec": metadata.get("codec"),
                "aspect_ratio": aspect_ratio,
                "motion_signal_level": extraction.get("motion_signal_level"),
                "has_audio": audio.get("has_audio"),
                "transcript_available": bool(audio.get("transcript")),
            },
        },
    }


def compile_fallback_prompts(
    blueprint: dict[str, Any],
    step1_data: dict[str, Any] | None,
) -> dict[str, Any]:
    try:
        metadata = step1_data.get("video_metadata", {}) if step1_data else {}
        return compile_prompts(blueprint, metadata)
    except Exception as err:
        print(f"Fallback prompt compilation failed: {err}", flush=True)
        return {}


def log_fallback_usage(
    fallback: FallbackMode,
    step_name: str,
    error: Exception | None = None,
) -> None:
    print("\n" + "═" * 60, flush=True)
    print("  ⚠️  FALLBACK MODE ACTIVE", flush=True)
    print("═" * 60, flush=True)
    print(f"  Step: {step_name}", flush=True)
    print(f"  Reason: {fallback.get_reason()}", flush=True)
    print(f"  Error: {str(error) if error else 'unknown'}", flush=True)
    print("─" * 60, flush=True)
    print("  Fallback generates approximate results", flush=True)
    print("  using local metadata only (no AI analysis).", flush=True)
    print("  For best quality, fix the underlying issue.", flush=True)
    print("═" * 60 + "\n", flush=True)
