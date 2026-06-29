#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.path_resolver import get_root
from utils.validation import BlueprintValidationError, validate_blueprint

PROJECT_ROOT = get_root()

LEGACY_FIELD_PATTERNS = {
    "camera": "camera_direction",
    "framing": "framing_type",
    "action": "action_and_motion",
    "environment": "environment_context",
}

MISSING_REQUIRED_FIELDS = {"start_time_seconds", "end_time_seconds"}


def _is_legacy_blueprint(blueprint: dict) -> bool:
    shots = blueprint.get("chronological_shots") or []
    if not shots:
        return False
    for shot in shots:
        shot_keys = set(shot.keys())
        if MISSING_REQUIRED_FIELDS - shot_keys:
            return True
        uses_old_names = any(old in shot_keys for old in LEGACY_FIELD_PATTERNS)
        if uses_old_names:
            return True
    return False


def _validate_file(filepath: str) -> dict:
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        blueprint = data.get("blueprint") if isinstance(data, dict) else None
        if not blueprint:
            return {"valid": True, "message": "No blueprint to validate"}

        if _is_legacy_blueprint(blueprint):
            return {"valid": True, "message": "Skipped (legacy schema — missing start_time_seconds/end_time_seconds)"}

        try:
            validate_blueprint(blueprint)
            return {"valid": True, "message": "Blueprint valid"}
        except BlueprintValidationError as e:
            return {"valid": False, "message": str(e)}
    except Exception as err:
        return {"valid": False, "message": str(err)}


def _latest_per_video(files: list[str]) -> list[str]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    timestamp_pat = re.compile(r"_(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})")
    for f in files:
        video_name = f.split("_")[0]
        match = timestamp_pat.search(f)
        ts = match.group(1) if match else ""
        grouped.setdefault(video_name, []).append((ts, f))
    result = []
    for _name, entries in grouped.items():
        entries.sort(key=lambda x: x[0], reverse=True)
        result.append(entries[0][1])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate output blueprints")
    parser.add_argument("--latest", action="store_true", help="Only validate the most recent output per video")
    args = parser.parse_args()

    print("═" * 60, flush=True)
    print("  VideoReverse — Validator", flush=True)
    print("═" * 60 + "\n", flush=True)

    output_dir = os.path.join(PROJECT_ROOT, "output_blueprints")
    if not os.path.exists(output_dir):
        print("  No output_blueprints directory found", flush=True)
        print("\n" + "═" * 60, flush=True)
        print("  ✅ No outputs to validate", flush=True)
        print("═" * 60 + "\n", flush=True)
        sys.exit(0)

    json_files = [f for f in os.listdir(output_dir) if f.endswith(".json")]
    if not json_files:
        print("  No JSON files found in output_blueprints", flush=True)
        print("\n" + "═" * 60, flush=True)
        print("  ✅ No outputs to validate", flush=True)
        print("═" * 60 + "\n", flush=True)
        sys.exit(0)

    if args.latest:
        json_files = _latest_per_video(json_files)
        print(f"  Validating latest output only ({len(json_files)} file(s))\n", flush=True)

    all_valid = True

    for file in json_files:
        filepath = os.path.join(output_dir, file)
        result = _validate_file(filepath)

        icon = "✅" if result["valid"] else "❌"
        print(f"{icon} {file}: {result['message']}", flush=True)

        if not result["valid"]:
            all_valid = False

    print("\n" + "═" * 60, flush=True)
    if all_valid:
        print("  ✅ All outputs valid", flush=True)
    else:
        print("  ❌ Some outputs invalid", flush=True)
    print("═" * 60 + "\n", flush=True)

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
