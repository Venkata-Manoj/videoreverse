from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.export import format_text


def _make_output(
    filename: str = "test.mp4",
    duration: float = 10.0,
    width: int = 1920,
    height: int = 1080,
    shots: list[dict] | None = None,
    prompts: dict | None = None,
) -> dict:
    if shots is None:
        shots = [
            {
                "shot_index": 0,
                "duration_seconds": 5.0,
                "camera_direction": "static",
                "framing_type": "wide",
                "action_and_motion": "person walking",
                "environment_context": "beach",
                "negative_elements": [],
            },
            {
                "shot_index": 1,
                "duration_seconds": 3.0,
                "camera_direction": "tracking",
                "framing_type": "close-up",
                "action_and_motion": "smile",
                "environment_context": "studio",
                "negative_elements": ["blur", "noise"],
            },
        ]
    if prompts is None:
        prompts = {
            "runway_gen4_5": {
                "label": "Runway Gen-4.5",
                "shots": [
                    {"shot_index": 0, "duration_seconds": 5.0, "aspect_ratio": "16:9", "prompt": "A wide shot of a person walking on a beach"},
                    {"shot_index": 1, "duration_seconds": 3.0, "aspect_ratio": "16:9", "prompt": "A close-up of a smile", "negative_prompt": "blur, noise"},
                ],
            }
        }
    return {
        "video_metadata": {
            "filename": filename,
            "duration_seconds": duration,
            "dimensions": f"{width}x{height}",
            "aspect_ratio": "16:9",
            "fps": 24,
        },
        "blueprint": {
            "global_aesthetic": {
                "art_style": "cinematic",
                "color_grading": "warm",
                "lighting_setup": "natural",
            },
            "chronological_shots": shots,
        },
        "prompts": prompts,
    }


def test_format_text_contains_header():
    result = format_text(_make_output())
    assert "VideoReverse" in result
    assert "Video Recreation Guide" in result


def test_format_text_contains_metadata():
    result = format_text(_make_output(filename="demo.mp4", duration=15.5))
    assert "demo.mp4" in result
    assert "15.5s" in result


def test_format_text_contains_resolution():
    result = format_text(_make_output(width=1280, height=720))
    assert "1280x720" in result


def test_format_text_contains_aesthetic():
    result = format_text(_make_output())
    assert "cinematic" in result
    assert "warm" in result
    assert "natural" in result


def test_format_text_contains_scene_breakdown():
    result = format_text(_make_output())
    assert "Scene Breakdown" in result
    assert "Shot 1" in result
    assert "Shot 2" in result


def test_format_text_contains_shot_details():
    shots = [
        {
            "shot_index": 0,
            "duration_seconds": 4.0,
            "camera_direction": "panning",
            "framing_type": "medium",
            "action_and_motion": "running",
            "environment_context": "city street",
            "negative_elements": ["cars"],
        }
    ]
    result = format_text(_make_output(shots=shots))
    assert "panning" in result
    assert "medium" in result
    assert "running" in result
    assert "city street" in result
    assert "cars" in result


def test_format_text_contains_prompts():
    result = format_text(_make_output())
    assert "Runway Gen-4.5" in result
    assert "A wide shot of a person walking on a beach" in result


def test_format_text_contains_negative_prompts():
    result = format_text(_make_output())
    assert "Negative:" in result
    assert "blur, noise" in result


def test_format_text_how_to_use_section():
    result = format_text(_make_output())
    assert "How to Use" in result
    assert "1." in result
    assert "5." in result


def test_format_text_empty_shots():
    output = _make_output(shots=[])
    result = format_text(output)
    assert "Scene Breakdown" in result


def test_format_text_empty_prompts():
    output = _make_output(prompts={})
    result = format_text(output)
    assert "Ready-to-Use Prompts by Model" in result


def test_format_text_missing_optional_fields():
    shots = [
        {
            "shot_index": 0,
            "duration_seconds": 2.0,
            "camera_direction": None,
            "framing_type": None,
            "action_and_motion": None,
            "environment_context": None,
            "negative_elements": [],
        }
    ]
    result = format_text(_make_output(shots=shots))
    assert "None" in result or "N/A" in result


def test_format_text_single_shot_no_shot_header():
    prompts = {
        "runway_gen4_5": {
            "label": "Runway Gen-4.5",
            "shots": [
                {"shot_index": 0, "duration_seconds": 5.0, "aspect_ratio": "16:9", "prompt": "test prompt"},
            ],
        }
    }
    result = format_text(_make_output(prompts=prompts))
    assert "test prompt" in result
    assert "Shot 1" not in result.split("Ready-to-Use")[1]


def test_format_text_multiple_models():
    prompts = {
        "runway_gen4_5": {
            "label": "Runway Gen-4.5",
            "shots": [{"shot_index": 0, "duration_seconds": 5.0, "aspect_ratio": "16:9", "prompt": "runway prompt"}],
        },
        "google_veo3_1": {
            "label": "Google Veo 3.1",
            "shots": [{"shot_index": 0, "duration_seconds": 5.0, "aspect_ratio": "16:9", "prompt": "veo prompt"}],
        },
    }
    result = format_text(_make_output(prompts=prompts))
    assert "Runway Gen-4.5" in result
    assert "Google Veo 3.1" in result
    assert "runway prompt" in result
    assert "veo prompt" in result


def test_format_text_returns_string():
    result = format_text(_make_output())
    assert isinstance(result, str)
    assert len(result) > 0
