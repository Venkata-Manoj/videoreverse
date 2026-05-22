#!/usr/bin/env python3
"""Verify an existing pipeline JSON output without rerunning the pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.path_resolver import get_root
from utils.validation import sanitize_blueprint, validate_blueprint

PROJECT_ROOT = get_root()


def find_latest_output(video_stem: str, output_dir: Path) -> Path | None:
    candidates = sorted(
        output_dir.glob(f"{video_stem}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def structural_checks(data: dict[str, Any]) -> dict[str, bool]:
    return {
        "has_video_metadata": bool(data.get("video_metadata")),
        "has_blueprint": bool(data.get("blueprint")),
        "has_prompts": bool(data.get("prompts")),
        "has_global_aesthetic": bool(data.get("blueprint", {}).get("global_aesthetic")),
        "has_chronological_shots": isinstance(data.get("blueprint", {}).get("chronological_shots"), list),
        "has_model_outputs": len(data.get("prompts", {})) > 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify saved VideoReverse output for a video.")
    parser.add_argument("video", nargs="?", default="test1.mp4", help="Source video name or path")
    parser.add_argument("-f", "--file", help="Specific JSON output file to verify")
    parser.add_argument("-o", "--output-dir", default="output_blueprints", help="Directory with pipeline JSON outputs")
    parser.add_argument("--strict", action="store_true", help="Also run full blueprint schema validation")
    args = parser.parse_args()

    video_stem = Path(args.video).stem
    expected_filename = f"{video_stem}.mp4"
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    if args.file:
        json_path = Path(args.file)
        if not json_path.is_absolute():
            json_path = PROJECT_ROOT / json_path
    else:
        json_path = find_latest_output(video_stem, output_dir)

    print("=" * 60)
    print("  VideoReverse - Output Verification")
    print("=" * 60)

    if json_path is None or not json_path.exists():
        print(f"\n  [x] No output found for '{video_stem}' in {output_dir}")
        print("  Run the pipeline first, or pass --file path/to/output.json")
        sys.exit(1)

    print(f"\n  File: {json_path.relative_to(PROJECT_ROOT)}")
    txt_path = json_path.with_suffix(".txt")
    if txt_path.exists():
        print(f"  Text: {txt_path.relative_to(PROJECT_ROOT)}")

    with open(json_path, encoding="utf-8") as handle:
        data = json.load(handle)

    checks = structural_checks(data)
    if data.get("video_metadata", {}).get("filename"):
        checks["metadata_filename_match"] = data["video_metadata"]["filename"] == expected_filename

    meta = data.get("video_metadata", {})
    shots = data.get("blueprint", {}).get("chronological_shots", [])
    prompts = data.get("prompts", {})

    print("\n  Video metadata:")
    for key in ("filename", "duration_seconds", "width", "height", "fps"):
        print(f"    {key}: {meta.get(key)}")

    print(f"\n  Blueprint: {len(shots)} shot(s)")
    for shot in shots:
        shot_index = shot.get("shot_index", "?")
        duration = shot.get("duration_seconds", "?")
        action = str(shot.get("action_and_motion", ""))[:72]
        print(f"    shot {shot_index} ({duration}s): {action}...")

    print(f"\n  Prompts: {len(prompts)} model(s)")
    for model_id, block in sorted(prompts.items()):
        print(f"    {model_id}: {len(block.get('shots', []))} shot prompt(s)")

    print("\n  Structural checks:")
    for name, ok in checks.items():
        print(f"    {'[ok]' if ok else '[x]'} {name}")

    score = sum(1 for value in checks.values() if value) / len(checks) * 100
    structural_ok = all(checks.values())

    strict_ok = True
    if args.strict and data.get("blueprint"):
        try:
            validate_blueprint(data["blueprint"])
            print("\n  Strict schema: [ok] valid")
        except Exception as err:
            strict_ok = False
            print(f"\n  Strict schema: [x] {err}")
            sanitized = sanitize_blueprint(data["blueprint"])
            try:
                validate_blueprint(sanitized)
                print("  Sanitized blueprint would pass strict validation")
            except Exception:
                pass

    print("\n" + "=" * 60)
    if structural_ok and (strict_ok or not args.strict):
        print(f"  [ok] Output OK (structural score {score:.0f}%)")
        print("=" * 60 + "\n")
        sys.exit(0)

    print(f"  [x] Output issues (structural score {score:.0f}%)")
    print("=" * 60 + "\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
