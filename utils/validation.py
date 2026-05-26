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


def sanitize_blueprint(blueprint: dict[str, Any] | None) -> dict[str, Any] | None:
    if not blueprint or not isinstance(blueprint, dict):
        return None
    try:
        blueprint_obj = UniversalBlueprint(**blueprint)
        return blueprint_obj.model_dump()
    except (ValidationError, TypeError):
        return None


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
