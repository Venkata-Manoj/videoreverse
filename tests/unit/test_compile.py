import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.compile import compile_prompts
from src.path_resolver import get_config_path
from tests.unit.test_framework import describe, it, expect

MOCK_BLUEPRINT = {
    'global_aesthetic': {
        'art_style': 'cinematic',
        'color_grading': 'warm',
        'lighting_setup': 'natural',
    },
    'chronological_shots': [
        {
            'shot_index': 0,
            'start_time_seconds': 0,
            'end_time_seconds': 5,
            'duration_seconds': 5,
            'camera_direction': 'static',
            'framing_type': 'wide',
            'action_and_motion': 'person walking',
            'environment_context': 'beach',
            'negative_elements': ['blur', 'noise'],
            'frame_references': [],
        },
        {
            'shot_index': 1,
            'start_time_seconds': 5,
            'end_time_seconds': 8,
            'duration_seconds': 3,
            'camera_direction': 'tracking',
            'framing_type': 'close-up',
            'action_and_motion': 'smile',
            'environment_context': 'studio',
            'negative_elements': [],
            'frame_references': [],
        },
    ],
}

MOCK_METADATA = {
    'width': 1920,
    'height': 1080,
}


def run_tests():
    def _test_all_models():
        prompts = compile_prompts(MOCK_BLUEPRINT, MOCK_METADATA)
        expect(len(prompts)).to_be_greater_than(0)
        expect(prompts.get('runway_gen4_5')).to_be_defined()
        expect(prompts.get('google_veo3_1')).to_be_defined()

    describe('compilePrompts', lambda: it('should generate prompts for all models', _test_all_models))

    def _test_shot_info():
        prompts = compile_prompts(MOCK_BLUEPRINT, MOCK_METADATA)
        runway = prompts['runway_gen4_5']
        expect(len(runway['shots'])).to_be(2)
        expect(runway['shots'][0]['shot_index']).to_be(0)
        expect(runway['shots'][0]['duration_seconds']).to_be(5)

    describe('compilePrompts', lambda: it('should include shot information in prompts', _test_shot_info))

    def _test_filter_models():
        prompts = compile_prompts(MOCK_BLUEPRINT, MOCK_METADATA, ['runway_gen4_5'])
        expect(len(prompts)).to_be(1)
        expect(prompts.get('runway_gen4_5')).to_be_defined()
        expect(prompts.get('google_veo3_1')).to_be_undefined()

    describe('compilePrompts', lambda: it('should filter models when filterModels provided', _test_filter_models))

    def _test_empty_negatives():
        no_negatives = {
            **MOCK_BLUEPRINT,
            'chronological_shots': [
                {
                    **MOCK_BLUEPRINT['chronological_shots'][0],
                    'negative_elements': [],
                },
            ],
        }
        prompts = compile_prompts(no_negatives, MOCK_METADATA)
        expect(prompts.get('runway_gen4_5')).to_be_defined()

    describe('compilePrompts', lambda: it('should handle empty negative_elements', _test_empty_negatives))

    def _test_luma_no_empty_keywords():
        with open(get_config_path("prompt_templates.json"), encoding="utf-8") as f:
            templates = json.load(f)
        luma = templates["luma_dream_machine"]
        keywords = luma["enhancement_rules"]["keyword_injection"]["brevity_keywords"]
        expect(all(k != "" for k in keywords)).to_be(True)
        expect(len(keywords)).to_be_greater_than(0)

    describe("Templates", lambda: it("luma brevity_keywords has no empty strings", _test_luma_no_empty_keywords))

    def _test_svd_no_camera_in_avoid_phrases():
        with open(get_config_path("prompt_templates.json"), encoding="utf-8") as f:
            templates = json.load(f)
        svd = templates["stable_video_diffusion"]
        phrases = svd["enhancement_rules"]["prompt_guidelines"]["avoid_phrases"]
        expect("the camera" not in phrases).to_be(True)

    describe("Templates", lambda: it("SVD avoid_phrases does not contradict {camera} placeholder", _test_svd_no_camera_in_avoid_phrases))

    def _test_no_model_has_camera_contradiction():
        with open(get_config_path("prompt_templates.json"), encoding="utf-8") as f:
            templates = json.load(f)
        for model_key, model_data in templates.items():
            if not isinstance(model_data, dict):
                continue
            template = model_data.get("template", "")
            if "{camera}" in template:
                avoid = model_data.get("enhancement_rules", {}).get("prompt_guidelines", {}).get("avoid_phrases", [])
                for phrase in avoid:
                    expect("camera" in phrase).to_be(False)

    describe("Templates", lambda: it("no model has camera-related avoid_phrases that contradict {camera} placeholder", _test_no_model_has_camera_contradiction))

    def _test_new_models_present():
        prompts = compile_prompts(MOCK_BLUEPRINT, MOCK_METADATA)
        expect("luma_ray2" in prompts).to_be(True)
        expect("pika_3_0" in prompts).to_be(True)
    describe("compilePrompts", lambda: it("luma_ray2 and pika_3_0 are present in compiled output", _test_new_models_present))

    def _test_new_model_labels():
        prompts = compile_prompts(MOCK_BLUEPRINT, MOCK_METADATA)
        expect(prompts["luma_ray2"]["label"]).to_equal("Luma Ray 2")
        expect(prompts["pika_3_0"]["label"]).to_equal("Pika 3.0")
    describe("compilePrompts", lambda: it("new models have correct labels", _test_new_model_labels))

    def _test_new_model_duration():
        prompts = compile_prompts(MOCK_BLUEPRINT, MOCK_METADATA)
        expect(prompts["luma_ray2"]["max_duration"]).to_be(10)
        expect(prompts["pika_3_0"]["max_duration"]).to_be(10)
    describe("compilePrompts", lambda: it("new models have correct max_duration", _test_new_model_duration))

    def _test_new_model_placeholders():
        with open(get_config_path("prompt_templates.json"), encoding="utf-8") as f:
            templates = json.load(f)
        core = ["{camera}", "{framing}", "{style}", "{action}", "{environment}", "{lighting}"]
        optional = ["{duration}", "{color_grading}", "{negative}"]
        for key in ["luma_ray2", "pika_3_0"]:
            tpl = templates[key]["template"]
            for ph in core:
                expect(ph in tpl).to_be(True)
            has_any_optional = any(ph in tpl for ph in optional)
            expect(has_any_optional).to_be(True)
    describe("Templates", lambda: it("new models contain all core placeholders + at least one optional", _test_new_model_placeholders))

    def _test_new_model_no_empty_keyword_lists():
        with open(get_config_path("prompt_templates.json"), encoding="utf-8") as f:
            templates = json.load(f)
        for key in ["luma_ray2", "pika_3_0"]:
            keywords = templates[key].get("enhancement_rules", {}).get("keyword_injection", {})
            for category, words in keywords.items():
                if isinstance(words, list):
                    expect(len(words)).to_be_greater_than(0)
                    for w in words:
                        expect(w != "").to_be(True)
    describe("Templates", lambda: it("new models have no empty keyword lists", _test_new_model_no_empty_keyword_lists))

    def _test_new_models_have_all_required_fields():
        with open(get_config_path("prompt_templates.json"), encoding="utf-8") as f:
            templates = json.load(f)
        required_fields = ["label", "template", "supports_negative", "max_duration", "aspect_ratio_support", "negative_placeholder", "notes", "enhancement_rules"]
        for key in ["luma_ray2", "pika_3_0"]:
            for field in required_fields:
                expect(field in templates[key]).to_be(True)
    describe("Templates", lambda: it("new models have all required fields", _test_new_models_have_all_required_fields))

    def _test_new_models_in_cli_list():
        from utils.cli import SUPPORTED_MODELS
        expect("luma_ray2" in SUPPORTED_MODELS).to_be(True)
        expect("pika_3_0" in SUPPORTED_MODELS).to_be(True)
    describe("Templates", lambda: it("new models are in SUPPORTED_MODELS", _test_new_models_in_cli_list))
