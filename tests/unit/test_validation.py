import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pydantic import ValidationError
from src.schemas.blueprint import (
    UniversalBlueprint,
    ChronologicalShot,
    GlobalAesthetic,
    FrameReference,
    ShotBoundary,
)
from utils.validation import validate_blueprint, sanitize_blueprint, validate_video_metadata
from tests.unit.test_framework import describe, it, expect


def _make_valid_shot(overrides: dict | None = None) -> dict:
    shot = {
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
    }
    if overrides:
        shot.update(overrides)
    return shot


def _make_valid_blueprint(overrides: dict | None = None) -> dict:
    bp = {
        'global_aesthetic': {
            'art_style': 'cinematic',
            'color_grading': 'warm',
            'lighting_setup': 'natural',
        },
        'chronological_shots': [_make_valid_shot()],
    }
    if overrides:
        bp.update(overrides)
    return bp


def _check(scenario: dict) -> None:
    try:
        validate_blueprint(scenario['blueprint'])
        passed = True
    except Exception:
        passed = False
    expect(passed).to_be(scenario['should_pass'])


def run_tests():
    # ── Existing validation scenarios (extended) ──
    test_scenarios = [
        {
            'name': 'valid blueprint',
            'blueprint': _make_valid_blueprint(),
            'should_pass': True,
        },
        {
            'name': 'valid blueprint with frame_references and shot_boundaries',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'frame_references': [
                        {'frame_index': 0, 'timestamp_seconds': 0.5, 'motion_level': 'low', 'relevance': 'key_frame'},
                        {'frame_index': 1, 'timestamp_seconds': 2.0, 'motion_level': 'high', 'relevance': 'supporting'},
                    ],
                    'shot_boundaries': {
                        'detected_by': 'motion_change',
                        'confidence': 'high',
                        'correlated_frames': [0, 1],
                    },
                })],
            }),
            'should_pass': True,
        },
        {
            'name': 'valid blueprint with audio_mood',
            'blueprint': _make_valid_blueprint({
                'global_aesthetic': {
                    'art_style': 'cinematic',
                    'color_grading': 'warm',
                    'lighting_setup': 'natural',
                    'audio_mood': 'dynamic',
                },
            }),
            'should_pass': True,
        },
        {
            'name': 'valid blueprint with extra unknown fields (tolerated)',
            'blueprint': _make_valid_blueprint({
                '_metadata': {'total_frames': 100, 'unknown_field': 'ignored'},
                'extra_root_field': 'should be ignored',
            }),
            'should_pass': True,
        },
        {
            'name': 'valid blueprint with multiple shots',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [
                    _make_valid_shot({'shot_index': 0, 'start_time_seconds': 0, 'end_time_seconds': 5, 'duration_seconds': 5}),
                    _make_valid_shot({'shot_index': 1, 'start_time_seconds': 5, 'end_time_seconds': 12, 'duration_seconds': 7}),
                    _make_valid_shot({'shot_index': 2, 'start_time_seconds': 12, 'end_time_seconds': 20, 'duration_seconds': 8}),
                ],
            }),
            'should_pass': True,
        },

        # Existing scenario: missing global_aesthetic
        {
            'name': 'missing global_aesthetic',
            'blueprint': {'chronological_shots': [_make_valid_shot()]},
            'should_pass': False,
        },
        # Existing scenario: missing required shot fields
        {
            'name': 'missing required shot fields',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [{'shot_index': 0}],
            }),
            'should_pass': False,
        },
        # Existing scenario: invalid shot_index (negative)
        {
            'name': 'invalid shot_index (negative)',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'shot_index': -1})],
            }),
            'should_pass': False,
        },

        # ── NEW edge cases ──

        # Null / non-dict inputs
        {
            'name': 'None blueprint',
            'blueprint': None,
            'should_pass': False,
        },
        {
            'name': 'empty dict blueprint',
            'blueprint': {},
            'should_pass': False,
        },
        {
            'name': 'list as blueprint',
            'blueprint': [],
            'should_pass': False,
        },
        {
            'name': 'string as blueprint',
            'blueprint': 'not a blueprint',
            'should_pass': False,
        },
        {
            'name': 'number as blueprint',
            'blueprint': 42,
            'should_pass': False,
        },

        # chronological_shots edge cases
        {
            'name': 'empty chronological_shots (violates min_length)',
            'blueprint': _make_valid_blueprint({'chronological_shots': []}),
            'should_pass': False,
        },
        {
            'name': 'chronological_shots is not a list',
            'blueprint': _make_valid_blueprint({'chronological_shots': 'not a list'}),
            'should_pass': False,
        },
        {
            'name': 'chronological_shots is None',
            'blueprint': {'global_aesthetic': {'art_style': 'x', 'color_grading': 'x', 'lighting_setup': 'x'}},
            'should_pass': False,
        },

        # Field type violations
        {
            'name': 'shot_index as string (type mismatch)',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'shot_index': 'zero'})],
            }),
            'should_pass': False,
        },
        {
            'name': 'start_time_seconds as string',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'start_time_seconds': 'not a number'})],
            }),
            'should_pass': False,
        },
        {
            'name': 'end_time_seconds as string',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'end_time_seconds': 'oops'})],
            }),
            'should_pass': False,
        },
        {
            'name': 'camera_direction as number',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'camera_direction': 123})],
            }),
            'should_pass': False,
        },

        # Numeric boundary violations
        {
            'name': 'start_time_seconds negative',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'start_time_seconds': -1})],
            }),
            'should_pass': False,
        },
        {
            'name': 'end_time_seconds negative',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'end_time_seconds': -5})],
            }),
            'should_pass': False,
        },
        {
            'name': 'duration_seconds zero (must be > 0)',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'duration_seconds': 0})],
            }),
            'should_pass': False,
        },
        {
            'name': 'duration_seconds negative',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'duration_seconds': -5})],
            }),
            'should_pass': False,
        },
        {
            'name': 'start_time_seconds equals end_time_seconds',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'start_time_seconds': 5, 'end_time_seconds': 5, 'duration_seconds': 5,
                })],
            }),
            'should_pass': False,
        },
        {
            'name': 'start_time_seconds greater than end_time_seconds',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'start_time_seconds': 10, 'end_time_seconds': 5, 'duration_seconds': 5,
                })],
            }),
            'should_pass': False,
        },

        # FrameReference edge cases
        {
            'name': 'frame_reference invalid motion_level',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'frame_references': [
                        {'frame_index': 0, 'timestamp_seconds': 0.5, 'motion_level': 'extreme', 'relevance': 'key_frame'},
                    ],
                })],
            }),
            'should_pass': False,
        },
        {
            'name': 'frame_reference invalid relevance',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'frame_references': [
                        {'frame_index': 0, 'timestamp_seconds': 0.5, 'motion_level': 'low', 'relevance': 'invalid'},
                    ],
                })],
            }),
            'should_pass': False,
        },
        {
            'name': 'frame_reference missing frame_index',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'frame_references': [
                        {'timestamp_seconds': 0.5, 'motion_level': 'low', 'relevance': 'key_frame'},
                    ],
                })],
            }),
            'should_pass': False,
        },
        {
            'name': 'frame_reference negative frame_index',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'frame_references': [
                        {'frame_index': -1, 'timestamp_seconds': 0.5, 'motion_level': 'low', 'relevance': 'key_frame'},
                    ],
                })],
            }),
            'should_pass': False,
        },
        {
            'name': 'frame_reference negative timestamp',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'frame_references': [
                        {'frame_index': 0, 'timestamp_seconds': -1, 'motion_level': 'low', 'relevance': 'key_frame'},
                    ],
                })],
            }),
            'should_pass': False,
        },
        {
            'name': 'frame_reference empty object',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'frame_references': [{}],
                })],
            }),
            'should_pass': False,
        },

        # ShotBoundary edge cases
        {
            'name': 'shot_boundaries invalid detected_by',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'shot_boundaries': {
                        'detected_by': 'magic',
                        'confidence': 'high',
                        'correlated_frames': [0],
                    },
                })],
            }),
            'should_pass': False,
        },
        {
            'name': 'shot_boundaries invalid confidence',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'shot_boundaries': {
                        'detected_by': 'motion_change',
                        'confidence': 'maybe',
                        'correlated_frames': [0],
                    },
                })],
            }),
            'should_pass': False,
        },
        {
            'name': 'shot_boundaries correlated_frames as non-list',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({
                    'shot_boundaries': {
                        'detected_by': 'motion_change',
                        'confidence': 'high',
                        'correlated_frames': 'not a list',
                    },
                })],
            }),
            'should_pass': False,
        },

        # negative_elements edge cases
        {
            'name': 'negative_elements is not a list',
            'blueprint': _make_valid_blueprint({
                'chronological_shots': [_make_valid_shot({'negative_elements': 'not a list'})],
            }),
            'should_pass': False,
        },
        {
            'name': 'negative_elements missing (defaults to [])',
            'blueprint': {
                'global_aesthetic': {'art_style': 'x', 'color_grading': 'x', 'lighting_setup': 'x'},
                'chronological_shots': [{
                    'shot_index': 0,
                    'start_time_seconds': 0,
                    'end_time_seconds': 5,
                    'duration_seconds': 5,
                    'camera_direction': 'static',
                    'framing_type': 'wide',
                    'action_and_motion': 'walking',
                    'environment_context': 'forest',
                    'frame_references': [],
                }],
            },
            'should_pass': True,  # Pydantic defaults missing optional fields
        },

        # GlobalAesthetic edge cases
        {
            'name': 'global_aesthetic missing art_style',
            'blueprint': _make_valid_blueprint({
                'global_aesthetic': {
                    'color_grading': 'warm',
                    'lighting_setup': 'natural',
                },
            }),
            'should_pass': False,
        },
        {
            'name': 'global_aesthetic empty art_style',
            'blueprint': _make_valid_blueprint({
                'global_aesthetic': {
                    'art_style': '',
                    'color_grading': 'warm',
                    'lighting_setup': 'natural',
                },
            }),
            'should_pass': True,  # Pydantic allows empty strings by default
        },
        {
            'name': 'global_aesthetic is not a dict',
            'blueprint': _make_valid_blueprint({'global_aesthetic': 'not a dict'}),
            'should_pass': False,
        },
    ]

    def _test_validate_blueprint():
        for scenario in test_scenarios:
            _check(scenario)

    describe('validateBlueprint', lambda: it(f'passes all {len(test_scenarios)} scenarios', _test_validate_blueprint))

    # ── Sanitize tests ──
    def _test_sanitize_basic():
        broken = {
            'global_aesthetic': {},
            'chronological_shots': [{}],
        }
        sanitized = sanitize_blueprint(broken)
        expect(sanitized['global_aesthetic']['art_style']).to_be('unknown')
        expect(sanitized['global_aesthetic']['color_grading']).to_be('unknown')
        expect(sanitized['chronological_shots'][0]['camera_direction']).to_be('static camera')

    describe('sanitizeBlueprint', lambda: it('should fill missing fields with defaults', _test_sanitize_basic))

    def _test_sanitize_none():
        expect(sanitize_blueprint(None)).to_be(None)

    describe('sanitizeBlueprint', lambda: it('should return None for None input', _test_sanitize_none))

    def _test_sanitize_empty_dict():
        expect(sanitize_blueprint({})).to_be(None)

    describe('sanitizeBlueprint', lambda: it('should return None for empty dict', _test_sanitize_empty_dict))

    def _test_sanitize_partial_good():
        data = {
            'global_aesthetic': {'art_style': 'test', 'color_grading': 'test', 'lighting_setup': 'test'},
            'chronological_shots': [
                {'shot_index': 0, 'start_time_seconds': 0, 'end_time_seconds': 5, 'duration_seconds': 5,
                 'camera_direction': 'tracking', 'framing_type': 'close-up', 'action_and_motion': 'running',
                 'environment_context': 'desert', 'negative_elements': [], 'frame_references': [
                    {'frame_index': 0, 'timestamp_seconds': 0.5, 'motion_level': 'low', 'relevance': 'key_frame'},
                ]},
            ],
        }
        sanitized = sanitize_blueprint(data)
        expect(sanitized['chronological_shots'][0]['action_and_motion']).to_be('running')
        expect(sanitized['chronological_shots'][0]['frame_references'][0]['frame_index']).to_be(0)

    describe('sanitizeBlueprint', lambda: it('should preserve valid data through sanitization', _test_sanitize_partial_good))

    def _test_sanitize_mixed_quality():
        data = {
            'global_aesthetic': {'art_style': 'test', 'color_grading': 'test', 'lighting_setup': 'test'},
            'chronological_shots': [
                {'shot_index': 0, 'start_time_seconds': 0, 'end_time_seconds': 5, 'duration_seconds': 5,
                 'camera_direction': None, 'framing_type': '', 'action_and_motion': 'walking',
                 'environment_context': 'park', 'negative_elements': None, 'frame_references': None},
            ],
        }
        sanitized = sanitize_blueprint(data)
        expect(sanitized['chronological_shots'][0]['camera_direction']).to_be('static camera')
        expect(sanitized['chronological_shots'][0]['negative_elements']).to_be([])
        expect(sanitized['chronological_shots'][0]['frame_references']).to_be([])

    describe('sanitizeBlueprint', lambda: it('should handle mixed null/empty fields gracefully', _test_sanitize_mixed_quality))

    # ── Video metadata tests ──
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
        invalid = {'filename': 'video.mp4'}
        expect(validate_video_metadata(invalid)).to_be(False)

    describe('validateVideoMetadata', lambda: it('should return false for missing fields', _test_invalid_metadata))

    def _test_metadata_zero_duration():
        expect(validate_video_metadata({'filename': 'v.mp4', 'duration_seconds': 0, 'width': 1920, 'height': 1080})).to_be(False)

    describe('validateVideoMetadata', lambda: it('should reject zero duration', _test_metadata_zero_duration))

    def _test_metadata_none():
        expect(validate_video_metadata(None)).to_be(False)

    describe('validateVideoMetadata', lambda: it('should return false for None input', _test_metadata_none))

    # ── Direct Pydantic model tests ──
    def _test_pydantic_valid():
        bp = UniversalBlueprint(
            global_aesthetic=GlobalAesthetic(art_style='cinematic', color_grading='warm', lighting_setup='natural'),
            chronological_shots=[
                ChronologicalShot(
                    shot_index=0, start_time_seconds=0, end_time_seconds=5, duration_seconds=5,
                    camera_direction='static', framing_type='wide', action_and_motion='walking',
                    environment_context='forest',
                ),
            ],
        )
        expect(bp.get_shot_count()).to_be(1)
        expect(bp.get_total_duration()).to_be(5.0)

    describe('Pydantic UniversalBlueprint', lambda: it('should construct valid model and compute helpers', _test_pydantic_valid))

    def _test_pydantic_model_dump():
        bp = UniversalBlueprint(
            global_aesthetic=GlobalAesthetic(art_style='cinematic', color_grading='warm', lighting_setup='natural'),
            chronological_shots=[
                ChronologicalShot(
                    shot_index=0, start_time_seconds=0, end_time_seconds=5, duration_seconds=5,
                    camera_direction='static', framing_type='wide', action_and_motion='walking',
                    environment_context='forest',
                ),
            ],
        )
        dumped = bp.model_dump()
        expect(dumped['global_aesthetic']['art_style']).to_be('cinematic')
        expect(dumped['chronological_shots'][0]['shot_index']).to_be(0)

    describe('Pydantic UniversalBlueprint', lambda: it('should serialize to dict via model_dump()', _test_pydantic_model_dump))

    def _test_pydantic_json_schema():
        schema = UniversalBlueprint.model_json_schema()
        expect(schema['type']).to_be('object')
        expect('global_aesthetic' in schema['properties']).to_be(True)
        expect('chronological_shots' in schema['properties']).to_be(True)
        expect('required' in schema or '$defs' in schema).to_be(True)

    describe('Pydantic UniversalBlueprint', lambda: it('should generate valid JSON schema', _test_pydantic_json_schema))

    def _test_pydantic_chronological_shot_validator():
        try:
            ChronologicalShot(
                shot_index=0, start_time_seconds=10, end_time_seconds=5, duration_seconds=5,
                camera_direction='static', framing_type='wide', action_and_motion='walking',
                environment_context='forest',
            )
            raise AssertionError('Expected ValidationError')
        except ValidationError:
            pass

    describe('Pydantic ChronologicalShot', lambda: it('should reject start >= end time', _test_pydantic_chronological_shot_validator))

    def _test_pydantic_shot_boundary():
        sb = ShotBoundary(detected_by='scene_cut', confidence='high', correlated_frames=[0, 5, 10])
        expect(sb.detected_by).to_be('scene_cut')
        expect(sb.correlated_frames).to_be([0, 5, 10])

    describe('Pydantic ShotBoundary', lambda: it('should construct with valid literals', _test_pydantic_shot_boundary))

    def _test_pydantic_frame_reference():
        fr = FrameReference(frame_index=3, timestamp_seconds=10.5, motion_level='high', relevance='transition_frame')
        expect(fr.frame_index).to_be(3)
        expect(fr.motion_level).to_be('high')

    describe('Pydantic FrameReference', lambda: it('should construct with valid literals', _test_pydantic_frame_reference))

    def _test_pydantic_global_aesthetic_defaults():
        ga = GlobalAesthetic(art_style='anime', color_grading='vibrant', lighting_setup='studio')
        expect(ga.audio_mood).to_be(None)

    describe('Pydantic GlobalAesthetic', lambda: it('should have optional audio_mood default to None', _test_pydantic_global_aesthetic_defaults))
