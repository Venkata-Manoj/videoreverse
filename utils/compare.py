from __future__ import annotations

import json
import os
from datetime import UTC
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


def compare_prompts(
    old_data: dict[str, Any] | None,
    new_data: dict[str, Any] | None,
) -> dict[str, Any]:
    results = {
        "timestamp": None,
        "models": {},
    }

    from datetime import datetime, timezone

    results["timestamp"] = datetime.now(UTC).isoformat()

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

        comparison = compare_prompts(baseline, new_data)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(comparison, f, indent=2)

        return comparison
    except Exception as err:
        print(f"Compare failed: {err}", flush=True)
        return None


def print_comparison(compare_result: dict[str, Any] | None) -> None:
    if not compare_result:
        print("No comparison data available.")
        return

    print("\n" + "═" * 60, flush=True)
    print("  Prompt Comparison Report", flush=True)
    print("═" * 60, flush=True)
    print(f"  Generated: {compare_result['timestamp']}\n", flush=True)

    for model, result in compare_result["models"].items():
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
