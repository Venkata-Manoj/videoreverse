from __future__ import annotations

from typing import Any


def calculate_shot_count_accuracy(blueprint: dict[str, Any], reference: dict[str, Any]) -> float:
    expected = len(reference.get("chronological_shots", []))
    actual = len(blueprint.get("chronological_shots", []))
    if expected == 0:
        return 1.0 if actual == 0 else 0.0
    return max(0.0, 1.0 - abs(actual - expected) / expected)


def calculate_style_match(blueprint: dict[str, Any], reference: dict[str, Any]) -> float:
    ref_style = reference.get("global_aesthetic", {}).get("art_style", "").lower()
    actual_style = blueprint.get("global_aesthetic", {}).get("art_style", "").lower()
    if not ref_style:
        return 1.0
    if not actual_style:
        return 0.0
    if ref_style == actual_style:
        return 1.0
    ref_words = set(ref_style.split())
    actual_words = set(actual_style.split())
    if not ref_words:
        return 0.0
    overlap = len(ref_words & actual_words)
    return overlap / len(ref_words)


def calculate_action_completeness(blueprint: dict[str, Any], reference: dict[str, Any]) -> float:
    ref_actions = [s.get("action", "").lower() for s in reference.get("chronological_shots", [])]
    actual_actions = [s.get("action", "").lower() for s in blueprint.get("chronological_shots", [])]
    if not ref_actions:
        return 1.0 if not actual_actions else 0.0
    matched = 0
    for ref_action in ref_actions:
        for actual_action in actual_actions:
            if ref_action in actual_action or actual_action in ref_action:
                matched += 1
                break
    return matched / len(ref_actions)


def calculate_camera_description_quality(blueprint: dict[str, Any], reference: dict[str, Any]) -> float:
    ref_cameras = [s.get("camera", "").lower() for s in reference.get("chronological_shots", [])]
    actual_cameras = [s.get("camera", "").lower() for s in blueprint.get("chronological_shots", [])]
    if not ref_cameras:
        return 1.0 if not actual_cameras else 0.5
    matched = 0
    for ref_cam in ref_cameras:
        for actual_cam in actual_cameras:
            if ref_cam in actual_cam or actual_cam in ref_cam:
                matched += 1
                break
    return matched / len(ref_cameras)


def calculate_prompt_specificity(blueprint: dict[str, Any]) -> float:
    shots = blueprint.get("chronological_shots", [])
    if not shots:
        return 0.0
    scores = []
    for shot in shots:
        action = shot.get("action", "")
        score = min(1.0, len(action.split()) / 10)
        has_details = any(
            keyword in action.lower()
            for keyword in ["camera", "pan", "zoom", "static", "close", "wide", "medium", "tracking", "tilt"]
        )
        if has_details:
            score = min(1.0, score + 0.2)
        scores.append(score)
    return sum(scores) / len(scores) if scores else 0.0


def calculate_lighting_environment_coverage(blueprint: dict[str, Any]) -> float:
    shots = blueprint.get("chronological_shots", [])
    if not shots:
        return 0.0
    fields_with_content = 0
    total_fields = len(shots) * 2
    for shot in shots:
        if shot.get("environment", "").strip():
            fields_with_content += 1
        if shot.get("lighting", "").strip():
            fields_with_content += 1
    return fields_with_content / total_fields if total_fields > 0 else 0.0


def calculate_frame_traceability(blueprint: dict[str, Any]) -> float:
    shots = blueprint.get("chronological_shots", [])
    if not shots:
        return 0.0
    shots_with_refs = sum(1 for s in shots if s.get("frame_references") and len(s["frame_references"]) > 0)
    return shots_with_refs / len(shots)


def calculate_overall_quality(
    blueprint: dict[str, Any],
    reference: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    if weights is None:
        weights = {
            "shot_count_accuracy": 0.15,
            "style_match": 0.20,
            "action_completeness": 0.25,
            "camera_description_quality": 0.15,
            "prompt_specificity": 0.10,
            "lighting_environment_coverage": 0.10,
            "frame_traceability": 0.05,
        }
    metrics = {
        "shot_count_accuracy": calculate_shot_count_accuracy(blueprint, reference),
        "style_match": calculate_style_match(blueprint, reference),
        "action_completeness": calculate_action_completeness(blueprint, reference),
        "camera_description_quality": calculate_camera_description_quality(blueprint, reference),
        "prompt_specificity": calculate_prompt_specificity(blueprint),
        "lighting_environment_coverage": calculate_lighting_environment_coverage(blueprint),
        "frame_traceability": calculate_frame_traceability(blueprint),
    }
    weighted_score = sum(metrics[k] * weights.get(k, 0) for k in metrics)
    normalized_weights_sum = sum(weights.get(k, 0) for k in metrics)
    if normalized_weights_sum > 0:
        weighted_score /= normalized_weights_sum
    grade = "A" if weighted_score >= 0.9 else "B" if weighted_score >= 0.75 else "C" if weighted_score >= 0.6 else "D" if weighted_score >= 0.4 else "F"
    return {
        "overall_score": round(weighted_score, 4),
        "grade": grade,
        "metrics": {k: round(v, 4) for k, v in metrics.items()},
        "weights_used": weights,
    }
