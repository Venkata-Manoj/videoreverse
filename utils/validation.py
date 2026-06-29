from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.schemas.blueprint import UniversalBlueprint


def validate_video_metadata(metadata: dict[str, Any] | None) -> bool:
    if not metadata:
        return False

    required = ["filename", "duration_seconds", "width", "height"]
    for field in required:
        if metadata.get(field) is None:
            return False

    return bool(metadata["duration_seconds"] > 0 and metadata["width"] > 0 and metadata["height"] > 0)


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


def _coerce_shot(shot: dict[str, Any], index: int) -> dict[str, Any]:
    out = dict(shot)
    if "shot_index" not in out or out["shot_index"] is None:
        out["shot_index"] = index
    ne = out.get("negative_elements")
    if isinstance(ne, str):
        out["negative_elements"] = [ne]
    elif ne is None:
        out["negative_elements"] = []
    if out.get("frame_references") is None:
        out["frame_references"] = []
    return out


def sanitize_blueprint(blueprint: dict[str, Any] | None) -> dict[str, Any] | None:
    if not blueprint or not isinstance(blueprint, dict):
        return None
    try:
        data = dict(blueprint)
        shots = data.get("chronological_shots", [])
        if isinstance(shots, list):
            data["chronological_shots"] = [_coerce_shot(s, i) for i, s in enumerate(shots)]
        blueprint_obj = UniversalBlueprint(**data)
        return blueprint_obj.model_dump()
    except (ValidationError, TypeError):
        return None
