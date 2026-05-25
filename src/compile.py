from __future__ import annotations

import json
import os
from typing import Any

from src.path_resolver import get_config_path


def _load_templates() -> dict[str, Any]:
    tpl_path = get_config_path("prompt_templates.json")
    if not os.path.exists(tpl_path):
        raise FileNotFoundError(f"prompt_templates.json not found at {tpl_path}")
    with open(tpl_path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def get_template_version() -> str:
    tpl_path = get_config_path("prompt_templates.json")
    if not os.path.exists(tpl_path):
        return "unknown"
    with open(tpl_path, encoding="utf-8") as f:
        data = json.load(f)
    return str(data.get("template_version", "unknown"))


def _resolve_aspect_ratio(width: int | None, height: int | None) -> str:
    if not width or not height:
        return "16:9"
    import math

    d = math.gcd(width, height)
    ratio = f"{width // d}:{height // d}"
    common = {"16:9": "16:9", "9:16": "9:16", "1:1": "1:1", "4:3": "4:3", "3:4": "3:4"}
    return common.get(ratio, "16:9")


def _fill_template(template: str, vars_dict: dict[str, str]) -> str:
    result = template
    for key, value in vars_dict.items():
        result = result.replace(f"{{{key}}}", value or "")
    import re

    result = re.sub(r"\s{2,}", " ", result)
    result = re.sub(r"\.\s*\.", ".", result)
    return result.strip()


def _apply_enhancement_rules(prompt: str, model_config: dict[str, Any]) -> str:
    rules = model_config.get("enhancement_rules")
    if not rules:
        return prompt

    enhanced = prompt
    guidelines = rules.get("prompt_guidelines", {})

    keywords = rules.get("keyword_injection", {})
    keyword_phrases = []

    for _category, words in keywords.items():
        if isinstance(words, list):
            keyword_phrases.extend(w for w in words if w and len(w) > 0)

    if keyword_phrases:
        lower_prompt = enhanced.lower()
        relevant_keywords = [
            kw
            for kw in keyword_phrases
            if kw.lower() not in lower_prompt and kw.lower().split(" ")[0] not in lower_prompt
        ]

        if relevant_keywords:
            inject_count = min(len(relevant_keywords), 2)
            to_inject = ", ".join(relevant_keywords[:inject_count])

            if (
                guidelines.get("emphasize_comma_format")
                or guidelines.get("emphasize_physics")
                or guidelines.get("emphasize_environment")
                or guidelines.get("emphasize_motion")
                or guidelines.get("emphasize_atmosphere")
                or guidelines.get("emphasize_temporal_flow")
                or guidelines.get("emphasize_style")
                or guidelines.get("emphasize_animation")
                or guidelines.get("emphasize_realism")
                or guidelines.get("emphasize_quality")
            ):
                enhanced = f"{enhanced}. {to_inject}."
            else:
                enhanced = f"{enhanced}. {to_inject}."

    if guidelines.get("avoid_adjectives"):
        import re

        for adj in guidelines["avoid_adjectives"]:
            enhanced = re.sub(rf"\b{re.escape(adj)}\b", "", enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r"\s{2,}", " ", enhanced).strip()

    if guidelines.get("max_length") and len(enhanced) > guidelines["max_length"]:
        truncated = enhanced[: guidelines["max_length"]]
        last_sentence_end = max(truncated.rfind(". "), truncated.rfind("! "), truncated.rfind("? "))
        if last_sentence_end > guidelines["max_length"] * 0.6:
            enhanced = truncated[: last_sentence_end + 1]
        else:
            enhanced = truncated

    enhanced = enhanced.rstrip(" .,").strip()

    return enhanced


def compile_prompts(
    blueprint: dict[str, Any],
    video_metadata: dict[str, Any] | None,
    filter_models: list[str] | None = None,
) -> dict[str, Any]:
    print("⚙️  VideoReverse: Step 6 — Prompt Compilation", flush=True)

    templates = _load_templates()
    shots = blueprint.get("chronological_shots", [])
    aesthetic = blueprint.get("global_aesthetic", {})
    aspect_ratio = _resolve_aspect_ratio(
        video_metadata.get("width") if video_metadata else None,
        video_metadata.get("height") if video_metadata else None,
    )

    if len(shots) == 0:
        raise ValueError("No chronological shots in blueprint")

    all_outputs = {}

    for model_key, model_config in templates.items():
        if filter_models and model_key not in filter_models:
            continue

        model_prompts = []

        for shot in shots:
            duration = min(shot.get("duration_seconds", 5), model_config.get("max_duration", 10))
            negative_text = ", ".join(shot.get("negative_elements", []))

            vars_dict = {
                "camera": shot.get("camera_direction", "static camera"),
                "framing": shot.get("framing_type", "medium shot"),
                "style": aesthetic.get("art_style", "cinematic photorealistic"),
                "action": shot.get("action_and_motion", ""),
                "environment": shot.get("environment_context", "neutral background"),
                "lighting": aesthetic.get("lighting_setup", "natural lighting"),
                "color_grading": aesthetic.get("color_grading", "natural color"),
                "duration": f"{duration:.1f}",
                "negative": (
                    (model_config.get("negative_placeholder", "") or "").replace("{negative}", negative_text)
                    if model_config.get("supports_negative") and negative_text
                    else ""
                ),
                "aspect_ratio": (
                    aspect_ratio
                    if model_config.get("aspect_ratio_support") and aspect_ratio in model_config["aspect_ratio_support"]
                    else (
                        model_config.get("aspect_ratio_support", ["16:9"])[0]
                        if model_config.get("aspect_ratio_support")
                        else "16:9"
                    )
                ),
            }

            prompt = _fill_template(model_config["template"], vars_dict)
            prompt = _apply_enhancement_rules(prompt, model_config)

            shot_output = {
                "shot_index": shot.get("shot_index", len(model_prompts)),
                "duration_seconds": duration,
                "aspect_ratio": vars_dict["aspect_ratio"],
                "prompt": prompt,
            }
            if model_config.get("supports_negative") and negative_text:
                shot_output["negative_prompt"] = negative_text

            model_prompts.append(shot_output)

        all_outputs[model_key] = {
            "label": model_config["label"],
            "max_duration": model_config.get("max_duration"),
            "aspect_ratio": _resolve_aspect_ratio(
                video_metadata.get("width") if video_metadata else None,
                video_metadata.get("height") if video_metadata else None,
            ),
            "shots": model_prompts,
        }

        print(f"   → {model_config['label']}: {len(model_prompts)} prompts compiled", flush=True)

    return all_outputs
