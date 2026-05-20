import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.compile import compile_prompts
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
