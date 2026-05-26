from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.schemas.blueprint import UniversalBlueprint


class BlueprintValidationError(Exception):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.name = "BlueprintValidationError"
        self.field = field


def validate_blueprint(blueprint: dict[str, Any]) -> bool:
    try:
        UniversalBlueprint(**blueprint)
        return True
    except ValidationError as e:
        errors = []
        for error in e.errors():
            loc = ".".join(str(loc_part) for loc_part in error["loc"])
            msg = error["msg"]
            errors.append(f"{loc}: {msg}")
        raise BlueprintValidationError("Validation failed:\n  - " + "\n  - ".join(errors)) from e


def _old_sanitize_blueprint(blueprint: dict[str, Any] | None) -> dict[str, Any] | None:
    if not blueprint:
        return None

    aesthetic = blueprint.get("global_aesthetic") or {}
    sanitized = {
        "global_aesthetic": {
            "art_style": aesthetic.get("art_style") or "unknown",
            "color_grading": aesthetic.get("color_grading") or "unknown",
            "lighting_setup": aesthetic.get("lighting_setup") or "unknown",
        },
        "chronological_shots": [],
    }

    for shot in blueprint.get("chronological_shots") or []:
        sanitized_shot = {
            "shot_index": shot.get("shot_index") if isinstance(shot.get("shot_index"), (int, float)) else 0,
            "start_time_seconds": shot.get("start_time_seconds")
            if isinstance(shot.get("start_time_seconds"), (int, float))
            else 0,
            "end_time_seconds": shot.get("end_time_seconds")
            if isinstance(shot.get("end_time_seconds"), (int, float))
            else 5,
            "duration_seconds": shot.get("duration_seconds")
            if isinstance(shot.get("duration_seconds"), (int, float)) and shot.get("duration_seconds", 0) > 0
            else 5,
            "camera_direction": shot.get("camera_direction") or "static camera",
            "framing_type": shot.get("framing_type") or "medium shot",
            "action_and_motion": shot.get("action_and_motion") or "no action",
            "environment_context": shot.get("environment_context") or "unknown environment",
            "negative_elements": shot.get("negative_elements")
            if isinstance(shot.get("negative_elements"), list)
            else [],
            "frame_references": shot.get("frame_references") if isinstance(shot.get("frame_references"), list)
            else [],
        }

        if shot.get("shot_boundaries") and isinstance(shot["shot_boundaries"], dict):
            sanitized_shot["shot_boundaries"] = {
                "detected_by": shot["shot_boundaries"].get("detected_by") or "manual",
                "confidence": shot["shot_boundaries"].get("confidence") or "medium",
                "correlated_frames": shot["shot_boundaries"].get("correlated_frames")
                if isinstance(shot["shot_boundaries"].get("correlated_frames"), list)
                else [],
            }

        sanitized["chronological_shots"].append(sanitized_shot)

    return sanitized


def sanitize_blueprint(blueprint: dict[str, Any] | None) -> dict[str, Any] | None:
    if not blueprint or not isinstance(blueprint, dict):
        return None
    try:
        blueprint_obj = UniversalBlueprint(**blueprint)
        return blueprint_obj.model_dump()
    except (ValidationError, TypeError):
        return _old_sanitize_blueprint(blueprint)


def validate_video_metadata(metadata: dict[str, Any] | None) -> bool:
    if not metadata:
        return False

    required = ["filename", "duration_seconds", "width", "height"]
    for field in required:
        if metadata.get(field) is None:
            return False

    return metadata["duration_seconds"] > 0 and metadata["width"] > 0 and metadata["height"] > 0


def validate_frame_traceability(
    blueprint: dict[str, Any],
    timeline_frames_count: int,
) -> list[dict[str, Any]]:
    issues = []

    for shot in blueprint.get("chronological_shots") or []:
        if not shot.get("frame_references") or len(shot["frame_references"]) == 0:
            issues.append(
                {
                    "shot_index": shot.get("shot_index"),
                    "issue": "No frame references found",
                    "severity": "warning",
                }
            )
            continue

        for ref in shot["frame_references"]:
            if ref.get("frame_index", 0) >= timeline_frames_count:
                issues.append(
                    {
                        "shot_index": shot.get("shot_index"),
                        "issue": f"Frame index {ref['frame_index']} exceeds timeline (max: {timeline_frames_count - 1})",
                        "severity": "error",
                        "frame_index": ref["frame_index"],
                    }
                )

        time_range = shot.get("end_time_seconds", 0) - shot.get("start_time_seconds", 0)
        refs_in_range = [
            r
            for r in shot["frame_references"]
            if shot.get("start_time_seconds", 0) <= r.get("timestamp_seconds", 0) <= shot.get("end_time_seconds", 0)
        ]

        if len(refs_in_range) == 0 and time_range > 3:
            issues.append(
                {
                    "shot_index": shot.get("shot_index"),
                    "issue": f"No frame references within shot time range ({shot.get('start_time_seconds', 0)}s - {shot.get('end_time_seconds', 0)}s)",
                    "severity": "warning",
                }
            )

    return issues
