from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_blueprint_mock(
    video_path: str,
    step1_data: dict[str, Any] | None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    print("🧪 Mock synthesis — generating synthetic blueprint from metadata (zero API cost)", flush=True)

    metadata = step1_data.get("video_metadata", {}) if step1_data else {}
    duration = float(metadata.get("duration_seconds", 0))

    shots = []
    if duration > 0:
        num_shots = max(1, round(duration / 5))
        seg = duration / num_shots
        for i in range(num_shots):
            start = round(i * seg, 1)
            end = round((i + 1) * seg, 1) if i < num_shots - 1 else round(duration, 1)
            shots.append(
                {
                    "shot_index": i,
                    "start_time_seconds": start,
                    "end_time_seconds": end,
                    "duration_seconds": round(end - start, 1),
                    "camera_direction": "static",
                    "framing_type": "medium",
                    "action_and_motion": "mock scene",
                    "environment_context": "indoor",
                    "negative_elements": [],
                    "frame_references": [],
                }
            )

    blueprint = {
        "global_aesthetic": {
            "art_style": "live-action",
            "color_grading": "natural",
            "lighting_setup": "natural",
        },
        "chronological_shots": shots,
        "_metadata": {
            "total_frames_analyzed": len(step1_data.get("timeline_frames", [])) if step1_data else 0,
            "shots_with_frame_traceability": 0,
            "analysis_timestamp": datetime.now(UTC).isoformat(),
            "synthesis_backend": "mock",
        },
    }

    print(f"   → {len(shots)} synthetic shots generated", flush=True)
    return blueprint
