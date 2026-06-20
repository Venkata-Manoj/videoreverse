from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.compile import compile_prompts
from src.export import format_text
from src.synthesize_mock import build_blueprint_mock
from utils.validation import sanitize_blueprint, validate_blueprint, validate_video_metadata

MOCK_STEP1_DATA = {
    "video_metadata": {
        "filename": "test.mp4",
        "duration_seconds": 15.0,
        "width": 1920,
        "height": 1080,
    },
    "timeline_frames": [
        {"frame_index": 0, "timestamp_seconds": 0.0},
        {"frame_index": 1, "timestamp_seconds": 2.5},
    ],
}


def test_mock_blueprint_generation():
    blueprint = build_blueprint_mock("/fake/video.mp4", MOCK_STEP1_DATA, {})
    assert blueprint is not None
    assert "global_aesthetic" in blueprint
    assert "chronological_shots" in blueprint
    assert len(blueprint["chronological_shots"]) > 0


def test_mock_blueprint_shot_count():
    blueprint = build_blueprint_mock("/fake/video.mp4", MOCK_STEP1_DATA, {})
    duration = MOCK_STEP1_DATA["video_metadata"]["duration_seconds"]
    expected_shots = max(1, round(duration / 5))
    assert len(blueprint["chronological_shots"]) == expected_shots


def test_mock_blueprint_metadata():
    blueprint = build_blueprint_mock("/fake/video.mp4", MOCK_STEP1_DATA, {})
    meta = blueprint.get("_metadata", {})
    assert meta["synthesis_backend"] == "mock"
    assert meta["total_frames_analyzed"] == 2


def test_mock_zero_duration():
    data = {
        "video_metadata": {"filename": "empty.mp4", "duration_seconds": 0},
        "timeline_frames": [],
    }
    blueprint = build_blueprint_mock("/fake/empty.mp4", data, {})
    assert blueprint is not None
    assert len(blueprint["chronological_shots"]) == 0


def test_mock_no_step1_data():
    blueprint = build_blueprint_mock("/fake/video.mp4", None, {})
    assert blueprint is not None
    assert "global_aesthetic" in blueprint


def test_mock_one_second_duration():
    data = {
        "video_metadata": {"filename": "short.mp4", "duration_seconds": 1.0},
        "timeline_frames": [],
    }
    blueprint = build_blueprint_mock("/fake/short.mp4", data, {})
    assert len(blueprint["chronological_shots"]) == 1


def test_full_mock_pipeline_compile():
    blueprint = build_blueprint_mock("/fake/video.mp4", MOCK_STEP1_DATA, {})
    metadata = MOCK_STEP1_DATA["video_metadata"]
    prompts = compile_prompts(blueprint, metadata)
    assert len(prompts) > 0
    for _model_key, model_data in prompts.items():
        assert "label" in model_data
        assert "shots" in model_data
        assert len(model_data["shots"]) > 0


def test_full_mock_pipeline_export():
    blueprint = build_blueprint_mock("/fake/video.mp4", MOCK_STEP1_DATA, {})
    metadata = MOCK_STEP1_DATA["video_metadata"]
    prompts = compile_prompts(blueprint, metadata)
    output = {
        "video_metadata": metadata,
        "blueprint": blueprint,
        "prompts": prompts,
    }
    text = format_text(output)
    assert isinstance(text, str)
    assert "VideoReverse" in text
    assert len(text) > 100


def test_validate_video_metadata_valid():
    assert validate_video_metadata(MOCK_STEP1_DATA["video_metadata"]) is True


def test_validate_video_metadata_none():
    assert validate_video_metadata(None) is False


def test_validate_video_metadata_missing_fields():
    assert validate_video_metadata({}) is False
    assert validate_video_metadata({"filename": "test.mp4"}) is False


def test_validate_video_metadata_negative_duration():
    meta = {"filename": "test.mp4", "duration_seconds": -1, "width": 100, "height": 100}
    assert validate_video_metadata(meta) is False


def test_validate_video_metadata_zero_dimensions():
    meta = {"filename": "test.mp4", "duration_seconds": 10, "width": 0, "height": 0}
    assert validate_video_metadata(meta) is False


def test_sanitize_blueprint_valid():
    blueprint = {
        "global_aesthetic": {
            "art_style": "cinematic",
            "color_grading": "warm",
            "lighting_setup": "natural",
        },
        "chronological_shots": [
            {
                "shot_index": 0,
                "start_time_seconds": 0,
                "end_time_seconds": 5,
                "duration_seconds": 5,
                "camera_direction": "static",
                "framing_type": "wide",
                "action_and_motion": "walking",
                "environment_context": "beach",
                "negative_elements": [],
                "frame_references": [],
            }
        ],
    }
    result = sanitize_blueprint(blueprint)
    assert result is not None
    assert "global_aesthetic" in result


def test_sanitize_blueprint_none():
    assert sanitize_blueprint(None) is None


def test_sanitize_blueprint_missing_shot_index():
    blueprint = {
        "global_aesthetic": {
            "art_style": "cinematic",
            "color_grading": "warm",
            "lighting_setup": "natural",
        },
        "chronological_shots": [
            {
                "start_time_seconds": 0,
                "end_time_seconds": 5,
                "duration_seconds": 5,
                "camera_direction": "static",
                "framing_type": "wide",
                "action_and_motion": "walking",
                "environment_context": "beach",
                "negative_elements": [],
                "frame_references": [],
            }
        ],
    }
    result = sanitize_blueprint(blueprint)
    assert result is not None
    assert result["chronological_shots"][0]["shot_index"] == 0


def test_sanitize_blueprint_string_negative_elements():
    blueprint = {
        "global_aesthetic": {
            "art_style": "cinematic",
            "color_grading": "warm",
            "lighting_setup": "natural",
        },
        "chronological_shots": [
            {
                "shot_index": 0,
                "start_time_seconds": 0,
                "end_time_seconds": 5,
                "duration_seconds": 5,
                "camera_direction": "static",
                "framing_type": "wide",
                "action_and_motion": "walking",
                "environment_context": "beach",
                "negative_elements": "blur",
                "frame_references": [],
            }
        ],
    }
    result = sanitize_blueprint(blueprint)
    assert result is not None
    assert isinstance(result["chronological_shots"][0]["negative_elements"], list)


def test_validate_blueprint_valid():
    blueprint = {
        "global_aesthetic": {
            "art_style": "cinematic",
            "color_grading": "warm",
            "lighting_setup": "natural",
        },
        "chronological_shots": [
            {
                "shot_index": 0,
                "start_time_seconds": 0,
                "end_time_seconds": 5,
                "duration_seconds": 5,
                "camera_direction": "static",
                "framing_type": "wide",
                "action_and_motion": "walking",
                "environment_context": "beach",
                "negative_elements": [],
                "frame_references": [],
            }
        ],
    }
    assert validate_blueprint(blueprint) is True


def test_validate_blueprint_empty_shots():
    blueprint = {
        "global_aesthetic": {
            "art_style": "cinematic",
            "color_grading": "warm",
            "lighting_setup": "natural",
        },
        "chronological_shots": [],
    }
    from utils.validation import BlueprintValidationError
    try:
        validate_blueprint(blueprint)
        raise AssertionError("Should have raised BlueprintValidationError")
    except BlueprintValidationError:
        pass


def test_compile_filter_models():
    blueprint = {
        "global_aesthetic": {
            "art_style": "cinematic",
            "color_grading": "warm",
            "lighting_setup": "natural",
        },
        "chronological_shots": [
            {
                "shot_index": 0,
                "start_time_seconds": 0,
                "end_time_seconds": 5,
                "duration_seconds": 5,
                "camera_direction": "static",
                "framing_type": "wide",
                "action_and_motion": "walking",
                "environment_context": "beach",
                "negative_elements": [],
                "frame_references": [],
            }
        ],
    }
    prompts = compile_prompts(blueprint, {"width": 1920, "height": 1080}, ["runway_gen4_5"])
    assert len(prompts) == 1
    assert "runway_gen4_5" in prompts
