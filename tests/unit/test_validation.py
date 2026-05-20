import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from utils.validation import validate_blueprint, sanitize_blueprint, validate_video_metadata
from tests.unit.test_framework import describe, it, expect


def run_tests():
    test_scenarios = [
        {
            'name': 'valid blueprint',
            'blueprint': {
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
                        'action_and_motion': 'character walking',
                        'environment_context': 'forest',
                        'negative_elements': [],
                        'frame_references': [],
                    },
                ],
            },
            'should_pass': True,
        },
        {
            'name': 'missing global_aesthetic',
            'blueprint': {
                'chronological_shots': [],
            },
            'should_pass': False,
        },
        {
            'name': 'missing required shot fields',
            'blueprint': {
                'global_aesthetic': {
                    'art_style': 'cinematic',
                    'color_grading': 'warm',
                    'lighting_setup': 'natural',
                },
                'chronological_shots': [
                    {
                        'shot_index': 0,
                    },
                ],
            },
            'should_pass': False,
        },
        {
            'name': 'invalid shot_index (negative)',
            'blueprint': {
                'global_aesthetic': {
                    'art_style': 'cinematic',
                    'color_grading': 'warm',
                    'lighting_setup': 'natural',
                },
                'chronological_shots': [
                    {
                        'shot_index': -1,
                        'start_time_seconds': 0,
                        'end_time_seconds': 5,
                        'duration_seconds': 5,
                        'camera_direction': 'static',
                        'framing_type': 'wide',
                        'action_and_motion': 'character walking',
                        'environment_context': 'forest',
                        'negative_elements': [],
                        'frame_references': [],
                    },
                ],
            },
            'should_pass': False,
        },
    ]

    def _test_validate_blueprint():
        for scenario in test_scenarios:
            try:
                validate_blueprint(scenario['blueprint'])
                passed = True
            except Exception:
                passed = False
            expect(passed).to_be(scenario['should_pass'])

    describe('validateBlueprint', lambda: it(f'passes all {len(test_scenarios)} scenarios', _test_validate_blueprint))

    def _test_sanitize():
        broken = {
            'global_aesthetic': {},
            'chronological_shots': [{}],
        }
        sanitized = sanitize_blueprint(broken)
        expect(sanitized['global_aesthetic']['art_style']).to_be('unknown')
        expect(sanitized['global_aesthetic']['color_grading']).to_be('unknown')
        expect(sanitized['chronological_shots'][0]['camera_direction']).to_be('static camera')

    describe('sanitizeBlueprint', lambda: it('should fill missing fields with defaults', _test_sanitize))

    def _test_valid_metadata():
        valid = {
            'filename': 'video.mp4',
            'duration_seconds': 10,
            'width': 1920,
            'height': 1080,
        }
        expect(validate_video_metadata(valid)).to_be(True)

    describe('validateVideoMetadata', lambda: it('should return true for valid metadata', _test_valid_metadata))

    def _test_invalid_metadata():
        invalid = {
            'filename': 'video.mp4',
        }
        expect(validate_video_metadata(invalid)).to_be(False)

    describe('validateVideoMetadata', lambda: it('should return false for missing fields', _test_invalid_metadata))
