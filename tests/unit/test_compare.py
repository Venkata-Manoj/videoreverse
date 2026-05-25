from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from utils.compare import (
    _get_levenshtein_similarity,
    compare_blueprints,
    compare_metadata,
    compare_outputs,
    compare_prompts,
    print_comparison,
    save_comparison,
)
from tests.unit.test_framework import describe, it, expect

MOCK_META_A = {
    "filename": "video_a.mp4",
    "duration_seconds": 30.0,
    "width": 1920,
    "height": 1080,
    "fps": 30.0,
    "codec": "h264",
    "aspect_ratio": "16:9",
    "bitrate_kbps": 5000,
}

MOCK_META_B = {
    "filename": "video_b.mp4",
    "duration_seconds": 45.0,
    "width": 3840,
    "height": 2160,
    "fps": 60.0,
    "codec": "h265",
    "aspect_ratio": "16:9",
    "bitrate_kbps": 15000,
}

MOCK_BP_A = {
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
            "action_and_motion": "character walking",
            "environment_context": "forest",
            "negative_elements": [],
            "frame_references": [],
        },
        {
            "shot_index": 1,
            "start_time_seconds": 5,
            "end_time_seconds": 10,
            "duration_seconds": 5,
            "camera_direction": "pan right",
            "framing_type": "medium",
            "action_and_motion": "character running",
            "environment_context": "forest",
            "negative_elements": [],
            "frame_references": [],
        },
    ],
}

MOCK_BP_B = {
    "global_aesthetic": {
        "art_style": "anime",
        "color_grading": "vibrant",
        "lighting_setup": "studio",
    },
    "chronological_shots": [
        {
            "shot_index": 0,
            "start_time_seconds": 0,
            "end_time_seconds": 10,
            "duration_seconds": 10,
            "camera_direction": "tracking",
            "framing_type": "close-up",
            "action_and_motion": "drone flying",
            "environment_context": "city",
            "negative_elements": [],
            "frame_references": [],
        },
    ],
}

MOCK_PROMPTS_A = {
    "runway_gen4_5": {
        "label": "Runway Gen-4.5",
        "shots": [
            {
                "shot_index": 0,
                "prompt": "wide shot of a person walking in a forest, warm lighting",
            },
            {
                "shot_index": 1,
                "prompt": "medium shot of a person running in a forest, pan right",
            },
        ],
    },
    "veo_3": {
        "label": "Veo 3",
        "shots": [
            {
                "shot_index": 0,
                "prompt": "wide shot of a person walking in a forest",
            },
        ],
    },
}

MOCK_PROMPTS_B = {
    "runway_gen4_5": {
        "label": "Runway Gen-4.5",
        "shots": [
            {
                "shot_index": 0,
                "prompt": "close-up of a drone flying over a city, vibrant colors",
            },
        ],
    },
    "kling_2": {
        "label": "Kling 2.0",
        "shots": [
            {
                "shot_index": 0,
                "prompt": "tracking shot of a drone over city",
            },
        ],
    },
}

OUTPUT_A = {
    "video_metadata": dict(MOCK_META_A),
    "blueprint": dict(MOCK_BP_A),
    "prompts": dict(MOCK_PROMPTS_A),
}

OUTPUT_B = {
    "video_metadata": dict(MOCK_META_B),
    "blueprint": dict(MOCK_BP_B),
    "prompts": dict(MOCK_PROMPTS_B),
}


def run_tests():
    describe("_get_levenshtein_similarity", _test_levenshtein)
    describe("compare_metadata", _test_compare_metadata)
    describe("compare_blueprints", _test_compare_blueprints)
    describe("compare_prompts", _test_compare_prompts)
    describe("compare_outputs", _test_compare_outputs)
    describe("print_comparison", _test_print_comparison)
    describe("save_comparison", _test_save_comparison)


def _test_levenshtein() -> None:
    def _identical() -> None:
        expect(_get_levenshtein_similarity("hello", "hello")).to_be(1.0)
    it("returns 1.0 for identical strings", _identical)

    def _completely_different() -> None:
        expect(_get_levenshtein_similarity("abc", "xyz")).to_be(0.0)
    it("returns 0.0 for completely different strings", _completely_different)

    def _empty_strings() -> None:
        expect(_get_levenshtein_similarity("", "")).to_be(1.0)
    it("returns 1.0 for both empty", _empty_strings)

    def _one_empty() -> None:
        sim = _get_levenshtein_similarity("hello", "")
        expect(sim).to_be(0.0)
    it("returns 0.0 when one is empty", _one_empty)

    def _partial_similarity() -> None:
        sim = _get_levenshtein_similarity("kitten", "sitten")
        expect(sim).to_be_greater_than(0.8)
        expect(sim).to_be_less_than_or_equal(1.0)
    it("computes partial similarity correctly", _partial_similarity)

    def _numeric_strings() -> None:
        expect(_get_levenshtein_similarity("12345", "12345")).to_be(1.0)
    it("handles numeric strings", _numeric_strings)


def _test_compare_metadata() -> None:
    def _identical_metadata() -> None:
        result = compare_metadata(OUTPUT_A, OUTPUT_A)
        expect(result["differences"]).to_equal({})
        expect(result["video_a"]["filename"]).to_equal("video_a.mp4")
        expect(result["video_b"]["filename"]).to_equal("video_a.mp4")
    it("returns empty differences for same metadata", _identical_metadata)

    def _different_metadata() -> None:
        result = compare_metadata(OUTPUT_A, OUTPUT_B)
        assert len(result["differences"]) > 0
        expect(result["differences"]["duration_seconds"]["video_a"]).to_be(30.0)
        expect(result["differences"]["duration_seconds"]["video_b"]).to_be(45.0)
    it("detects differences between two videos", _different_metadata)

    def _none_input() -> None:
        result = compare_metadata(None, None)
        expect(result["video_a"]["filename"]).to_be(None)
        expect(result["differences"]).to_equal({})
    it("handles None inputs gracefully", _none_input)

    def _first_only() -> None:
        result = compare_metadata(OUTPUT_A, None)
        expect(result["video_a"]["filename"]).to_equal("video_a.mp4")
        expect(result["video_b"]["filename"]).to_be(None)
    it("handles only first output provided", _first_only)

    def _second_only() -> None:
        result = compare_metadata(None, OUTPUT_B)
        expect(result["video_a"]["filename"]).to_be(None)
        expect(result["video_b"]["filename"]).to_equal("video_b.mp4")
    it("handles only second output provided", _second_only)


def _test_compare_blueprints() -> None:
    def _identical_blueprint() -> None:
        result = compare_blueprints(OUTPUT_A, OUTPUT_A)
        expect(result["aesthetic"]["differences"]).to_equal({})
        expect(result["shots"]["count_difference"]).to_be(0)
        expect(len(result["shots"]["details"])).to_be(0)
    it("returns no diffs for same blueprint", _identical_blueprint)

    def _different_aesthetic() -> None:
        result = compare_blueprints(OUTPUT_A, OUTPUT_B)
        diffs = result["aesthetic"]["differences"]
        assert "art_style" in diffs
        expect(diffs["art_style"]["video_a"]).to_equal("cinematic")
        expect(diffs["art_style"]["video_b"]).to_equal("anime")
    it("detects aesthetic differences", _different_aesthetic)

    def _different_shot_count() -> None:
        result = compare_blueprints(OUTPUT_A, OUTPUT_B)
        expect(result["shots"]["video_a_count"]).to_be(2)
        expect(result["shots"]["video_b_count"]).to_be(1)
        expect(result["shots"]["count_difference"]).to_be(1)
    it("reports shot count differences", _different_shot_count)

    def _shot_details_modified() -> None:
        result = compare_blueprints(OUTPUT_A, OUTPUT_B)
        modified = [s for s in result["shots"]["details"] if s["status"] == "modified"]
        assert len(modified) == 1
        diffs = modified[0]["differences"]
        assert "camera_direction" in diffs
        expect(diffs["camera_direction"]["video_a"]).to_equal("static")
        expect(diffs["camera_direction"]["video_b"]).to_equal("tracking")
    it("reports per-shot field differences", _shot_details_modified)

    def _none_input() -> None:
        result = compare_blueprints(None, None)
        expect(result["shots"]["video_a_count"]).to_be(0)
        expect(result["shots"]["video_b_count"]).to_be(0)
    it("handles None inputs", _none_input)


def _test_compare_prompts() -> None:
    def _same_prompts() -> None:
        result = compare_prompts(OUTPUT_A, OUTPUT_A)
        for model, data in result["models"].items():
            expect(data["status"]).to_equal("unchanged")
            expect(data["similarity"]).to_be(100)
    it("returns unchanged for same prompts", _same_prompts)

    def _modified_prompt() -> None:
        result = compare_prompts(OUTPUT_A, OUTPUT_B)
        model = result["models"].get("runway_gen4_5")
        assert model is not None
        expect(model["status"]).to_equal("modified")
        expect(model["similarity"]).to_be_less_than_or_equal(100)
        assert len(model["changes"]) > 0
    it("detects modified prompts in same model", _modified_prompt)

    def _new_model() -> None:
        result = compare_prompts(OUTPUT_A, OUTPUT_B)
        model = result["models"].get("kling_2")
        assert model is not None
        expect(model["status"]).to_equal("new")
    it("flags new model as added", _new_model)

    def _removed_model() -> None:
        result = compare_prompts(OUTPUT_B, OUTPUT_A)
        model = result["models"].get("kling_2")
        assert model is not None
        expect(model["status"]).to_equal("removed")
    it("flags removed model as removed", _removed_model)

    def _none_input() -> None:
        result = compare_prompts(None, None)
        expect(result["models"]).to_equal({})
    it("handles None inputs", _none_input)

    def _first_none() -> None:
        result = compare_prompts(None, OUTPUT_B)
        for model, data in result["models"].items():
            expect(data["status"]).to_equal("new")
    it("handles first output None", _first_none)

    def _second_none() -> None:
        result = compare_prompts(OUTPUT_A, None)
        for model, data in result["models"].items():
            expect(data["status"]).to_equal("removed")
    it("handles second output None", _second_none)


def _test_compare_outputs() -> None:
    def _full_comparison() -> None:
        result = compare_outputs(OUTPUT_A, OUTPUT_B)
        expect(result["video_a_label"]).to_equal("video_a.mp4")
        expect(result["video_b_label"]).to_equal("video_b.mp4")
        assert "timestamp" in result
        assert "metadata" in result
        assert "blueprint" in result
        assert "prompts" in result
    it("produces complete comparison output", _full_comparison)

    def _compare_same() -> None:
        result = compare_outputs(OUTPUT_A, OUTPUT_A)
        meta_diffs = result["metadata"]["differences"]
        bp_diffs = result["blueprint"]["aesthetic"]["differences"]
        expect(meta_diffs).to_equal({})
        expect(bp_diffs).to_equal({})
    it("returns no diffs when comparing same output", _compare_same)

    def _compare_none_none() -> None:
        result = compare_outputs(None, None)
        expect(result["video_a_label"]).to_equal("video_a")
        expect(result["video_b_label"]).to_equal("video_b")
    it("handles None for both outputs", _compare_none_none)

    def _labels_from_metadata() -> None:
        a = {"video_metadata": {"filename": "my_video.mp4"}, "blueprint": {}, "prompts": {}}
        b = {"video_metadata": {}, "blueprint": {}, "prompts": {}}
        result = compare_outputs(a, b)
        expect(result["video_a_label"]).to_equal("my_video.mp4")
        expect(result["video_b_label"]).to_equal("video_b")
    it("extracts labels from metadata filenames", _labels_from_metadata)


def _test_print_comparison() -> None:
    def _none_input() -> None:
        try:
            print_comparison(None)
        except Exception:
            expect(True).to_be(False)
    it("does not crash with None input", _none_input)

    def _empty_input() -> None:
        try:
            print_comparison({})
        except Exception:
            expect(True).to_be(False)
    it("does not crash with empty dict", _empty_input)

    def _full_data() -> None:
        result = compare_outputs(OUTPUT_A, OUTPUT_B)
        try:
            print_comparison(result)
        except Exception:
            expect(True).to_be(False)
    it("does not crash with full comparison data", _full_data)


def _test_save_comparison() -> None:
    def _save_to_temp() -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(OUTPUT_A, f)
            baseline = f.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(OUTPUT_B, f)
            new_file = f.name

        out_path = baseline.replace(".json", "_compare.json")
        try:
            result = save_comparison(baseline, new_file, output_path=out_path)
            assert result is not None
            assert "metadata" in result
            assert os.path.exists(out_path)
            with open(out_path, encoding="utf-8") as f:
                saved = json.load(f)
                expect(saved["video_a_label"]).to_equal("video_a.mp4")
                expect(saved["video_b_label"]).to_equal("video_b.mp4")
        finally:
            for p in [baseline, new_file, out_path]:
                if os.path.exists(p):
                    os.unlink(p)
    it("saves comparison to file and returns result", _save_to_temp)

    def _missing_files() -> None:
        result = save_comparison("/nonexistent/baseline.json", "/nonexistent/new.json")
        expect(result).to_be(None)
    it("returns None for missing files", _missing_files)

    def _no_output_path() -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(OUTPUT_A, f)
            baseline = f.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(OUTPUT_B, f)
            new_file = f.name
        try:
            result = save_comparison(baseline, new_file, output_path=None)
            assert result is not None
            expect(result["video_a_label"]).to_equal("video_a.mp4")
        finally:
            for p in [baseline, new_file]:
                if os.path.exists(p):
                    os.unlink(p)
    it("returns result even without output path", _no_output_path)
