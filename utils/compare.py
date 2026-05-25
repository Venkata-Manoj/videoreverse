from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_COMPARE_DIR = Path(__file__).resolve().parent.parent / "test_results"


def _get_levenshtein_similarity(str1: str, str2: str) -> float:
    len1 = len(str1)
    len2 = len(str2)

    matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        matrix[i][0] = i
    for j in range(len2 + 1):
        matrix[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if str1[i - 1] == str2[j - 1] else 1
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j - 1] + cost)

    max_len = max(len1, len2)
    if max_len == 0:
        return 1.0

    return 1 - (matrix[len1][len2] / max_len)


def _safe_get(data: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
    return data if data is not None else default


def compare_metadata(
    output_a: dict[str, Any] | None,
    output_b: dict[str, Any] | None,
) -> dict[str, Any]:
    meta_a = (output_a or {}).get("video_metadata") or {}
    meta_b = (output_b or {}).get("video_metadata") or {}

    fields = ["filename", "duration_seconds", "width", "height", "fps", "codec", "aspect_ratio", "bitrate_kbps"]
    diffs = {}
    for field in fields:
        va = meta_a.get(field)
        vb = meta_b.get(field)
        if va != vb:
            diffs[field] = {"video_a": va, "video_b": vb}

    return {
        "video_a": {
            "filename": meta_a.get("filename"),
            "duration_seconds": meta_a.get("duration_seconds"),
            "dimensions": f"{meta_a.get('width')}x{meta_a.get('height')}",
            "fps": meta_a.get("fps"),
            "codec": meta_a.get("codec"),
            "aspect_ratio": meta_a.get("aspect_ratio"),
        },
        "video_b": {
            "filename": meta_b.get("filename"),
            "duration_seconds": meta_b.get("duration_seconds"),
            "dimensions": f"{meta_b.get('width')}x{meta_b.get('height')}",
            "fps": meta_b.get("fps"),
            "codec": meta_b.get("codec"),
            "aspect_ratio": meta_b.get("aspect_ratio"),
        },
        "differences": diffs,
    }


def compare_blueprints(
    output_a: dict[str, Any] | None,
    output_b: dict[str, Any] | None,
) -> dict[str, Any]:
    bp_a = (output_a or {}).get("blueprint") or {}
    bp_b = (output_b or {}).get("blueprint") or {}

    aesthetic_a = bp_a.get("global_aesthetic") or {}
    aesthetic_b = bp_b.get("global_aesthetic") or {}

    aesthetic_diffs = {}
    for key in ["art_style", "color_grading", "lighting_setup"]:
        va = aesthetic_a.get(key)
        vb = aesthetic_b.get(key)
        if va != vb:
            aesthetic_diffs[key] = {"video_a": va, "video_b": vb}

    shots_a = bp_a.get("chronological_shots") or []
    shots_b = bp_b.get("chronological_shots") or []

    shot_count_diff = len(shots_a) - len(shots_b)

    shot_details = []
    for i in range(max(len(shots_a), len(shots_b))):
        sa = shots_a[i] if i < len(shots_a) else None
        sb = shots_b[i] if i < len(shots_b) else None

        if sa is None:
            shot_details.append({"shot_index": i, "status": "added_in_b"})
        elif sb is None:
            shot_details.append({"shot_index": i, "status": "removed_in_b"})
        else:
            diffs = {}
            for field in ["camera_direction", "framing_type", "action_and_motion", "environment_context", "duration_seconds"]:
                if sa.get(field) != sb.get(field):
                    diffs[field] = {"video_a": sa.get(field), "video_b": sb.get(field)}
            if diffs:
                shot_details.append({"shot_index": i, "status": "modified", "differences": diffs})

    total_a = sum(s.get("duration_seconds", 0) or 0 for s in shots_a)
    total_b = sum(s.get("duration_seconds", 0) or 0 for s in shots_b)

    return {
        "aesthetic": {
            "video_a": dict(aesthetic_a),
            "video_b": dict(aesthetic_b),
            "differences": aesthetic_diffs,
        },
        "shots": {
            "video_a_count": len(shots_a),
            "video_b_count": len(shots_b),
            "count_difference": shot_count_diff,
            "details": shot_details,
        },
        "total_duration": {
            "video_a": round(total_a, 1),
            "video_b": round(total_b, 1),
        },
    }


def compare_prompts(
    old_data: dict[str, Any] | None,
    new_data: dict[str, Any] | None,
) -> dict[str, Any]:
    results: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "models": {},
    }

    old_prompts = old_data.get("prompts", {}) if old_data else {}
    new_prompts = new_data.get("prompts", {}) if new_data else {}

    all_models = set(list(old_prompts.keys()) + list(new_prompts.keys()))

    for model in all_models:
        old_model = old_prompts.get(model)
        new_model = new_prompts.get(model)

        if not old_model:
            results["models"][model] = {"status": "new", "change": "added"}
            continue
        if not new_model:
            results["models"][model] = {"status": "removed", "change": "removed"}
            continue

        old_shots = old_model.get("shots", [])
        new_shots = new_model.get("shots", [])

        prompt_changes = []
        for i in range(max(len(old_shots), len(new_shots))):
            old_prompt = old_shots[i].get("prompt", "") if i < len(old_shots) else ""
            new_prompt = new_shots[i].get("prompt", "") if i < len(new_shots) else ""

            if old_prompt != new_prompt:
                levenshtein = _get_levenshtein_similarity(old_prompt, new_prompt)
                prompt_changes.append(
                    {
                        "shot_index": i,
                        "similarity": round(levenshtein * 100),
                        "old_length": len(old_prompt),
                        "new_length": len(new_prompt),
                    }
                )

        avg_similarity = sum(c["similarity"] for c in prompt_changes) / len(prompt_changes) if prompt_changes else 100

        results["models"][model] = {
            "status": "unchanged" if avg_similarity == 100 else "modified",
            "similarity": round(avg_similarity),
            "changes": prompt_changes,
            "shots_count": len(new_shots),
        }

    return results


def compare_outputs(
    output_a: dict[str, Any] | None,
    output_b: dict[str, Any] | None,
) -> dict[str, Any]:
    comparison = {
        "timestamp": datetime.now(UTC).isoformat(),
        "metadata": compare_metadata(output_a, output_b),
        "blueprint": compare_blueprints(output_a, output_b),
        "prompts": compare_prompts(output_a, output_b),
    }

    comparison["video_a_label"] = _safe_get(output_a, "video_metadata", "filename", default="video_a")
    comparison["video_b_label"] = _safe_get(output_b, "video_metadata", "filename", default="video_b")

    return comparison


def _print_prompt_report(compare_result: dict[str, Any] | None) -> None:
    if not compare_result:
        print("No comparison data available.")
        return

    print("\n" + "═" * 60, flush=True)
    print("  Prompt Comparison Report", flush=True)
    print("═" * 60, flush=True)
    print(f"  Generated: {compare_result.get('timestamp', 'N/A')}\n", flush=True)

    for model, result in (compare_result.get("models") or {}).items():
        status_icon = (
            "✓"
            if result["status"] == "unchanged"
            else "+"
            if result["status"] == "new"
            else "-"
            if result["status"] == "removed"
            else "~"
        )

        print(f"  {status_icon} {model}", flush=True)
        print(f"     Status: {result['status']}", flush=True)
        print(f"     Similarity: {result.get('similarity', 0)}%", flush=True)
        if "shots_count" in result:
            print(f"     Shots: {result['shots_count']}", flush=True)
        if result.get("changes") and len(result["changes"]) > 0:
            print(f"     Changed shots: {len(result['changes'])}", flush=True)
        print(flush=True)

    print("═" * 60 + "\n", flush=True)


def print_comparison(compare_result: dict[str, Any] | None) -> None:
    if not compare_result:
        print("No comparison data available.")
        return

    if "models" in compare_result and "video_a_label" not in compare_result:
        _print_prompt_report(compare_result)
        return

    label_a = compare_result.get("video_a_label", "Video A")
    label_b = compare_result.get("video_b_label", "Video B")

    print("\n" + "═" * 60, flush=True)
    print("  Video Comparison Report", flush=True)
    print("═" * 60, flush=True)
    print(f"  Generated: {compare_result.get('timestamp', 'N/A')}\n", flush=True)

    meta = compare_result.get("metadata", {})
    print(f"  ── Metadata ──", flush=True)
    for side, label in [("video_a", label_a), ("video_b", label_b)]:
        v = meta.get(side, {})
        dur = v.get("duration_seconds", "?")
        print(f"  {label}: {v.get('filename', '?')}  |  {dur}s  |  {v.get('dimensions', '?')}  |  {v.get('fps', '?')}fps", flush=True)
    if meta.get("differences"):
        print(f"  Differences: {len(meta['differences'])} field(s)", flush=True)
        for key, diff in meta["differences"].items():
            print(f"    {key}: {diff.get('video_a')} -> {diff.get('video_b')}", flush=True)
    print(flush=True)

    bp = compare_result.get("blueprint", {})
    print(f"  ── Blueprint ──", flush=True)
    aest = bp.get("aesthetic", {})
    if aest.get("differences"):
        print(f"  Aesthetic differences:", flush=True)
        for key, diff in aest["differences"].items():
            print(f"    {key}: {diff.get('video_a')} -> {diff.get('video_b')}", flush=True)
    else:
        print(f"  Aesthetic: identical", flush=True)

    shots = bp.get("shots", {})
    print(f"  Shots: {label_a}={shots.get('video_a_count', 0)}, {label_b}={shots.get('video_b_count', 0)}", flush=True)
    if shots.get("details"):
        print(f"  Shot differences: {len(shots['details'])} shot(s)", flush=True)
        for sd in shots["details"]:
            status = sd.get("status", "unknown")
            idx = sd.get("shot_index", "?")
            if status == "modified":
                diffs = sd.get("differences", {})
                diff_str = ", ".join(f"{k}: {v.get('video_a')}->{v.get('video_b')}" for k, v in diffs.items())
                print(f"    Shot {idx}: {diff_str}", flush=True)
            elif status == "added_in_b":
                print(f"    Shot {idx}: added in {label_b}", flush=True)
            elif status == "removed_in_b":
                print(f"    Shot {idx}: not in {label_b}", flush=True)
    print(flush=True)

    prompts = compare_result.get("prompts", {})
    print(f"  ── Prompts ──", flush=True)
    for model, result in prompts.get("models", {}).items():
        if result["status"] == "unchanged":
            continue
        status_icon = {"new": "+", "removed": "-", "modified": "~"}.get(result["status"], "?")
        sim = result.get("similarity", 100)
        print(f"  {status_icon} {model}  ({sim}% similar)", flush=True)
    print(flush=True)

    print("═" * 60 + "\n", flush=True)


def save_comparison(
    baseline_path: str,
    new_path: str,
    output_path: str | None = None,
) -> dict[str, Any] | None:
    try:
        with open(baseline_path, encoding="utf-8") as f:
            baseline = json.load(f)
        with open(new_path, encoding="utf-8") as f:
            new_data = json.load(f)

        comparison = compare_outputs(baseline, new_data)

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(comparison, f, indent=2)

        return comparison
    except Exception as err:
        print(f"Compare failed: {err}", flush=True)
        return None
