import { validateBlueprint, sanitizeBlueprint, validateVideoMetadata } from '../utils/validation.js';
import { describe, it, expect } from './test-framework.js';

const testScenarios = [
    {
        name: 'valid blueprint',
        blueprint: {
            global_aesthetic: {
                art_style: 'cinematic',
                color_grading: 'warm',
                lighting_setup: 'natural',
            },
            chronological_shots: [
                {
                    shot_index: 0,
                    duration_seconds: 5,
                    camera_direction: 'static',
                    framing_type: 'wide',
                    action_and_motion: 'character walking',
                    environment_context: 'forest',
                    negative_elements: [],
                },
            ],
        },
        shouldPass: true,
    },
    {
        name: 'missing global_aesthetic',
        blueprint: {
            chronological_shots: [],
        },
        shouldPass: false,
    },
    {
        name: 'missing required shot fields',
        blueprint: {
            global_aesthetic: {
                art_style: 'cinematic',
                color_grading: 'warm',
                lighting_setup: 'natural',
            },
            chronological_shots: [
                {
                    shot_index: 0,
                },
            ],
        },
        shouldPass: false,
    },
    {
        name: 'invalid shot_index (negative)',
        blueprint: {
            global_aesthetic: {
                art_style: 'cinematic',
                color_grading: 'warm',
                lighting_setup: 'natural',
            },
            chronological_shots: [
                {
                    shot_index: -1,
                    duration_seconds: 5,
                    camera_direction: 'static',
                    framing_type: 'wide',
                    action_and_motion: 'character walking',
                    environment_context: 'forest',
                    negative_elements: [],
                },
            ],
        },
        shouldPass: false,
    },
];

describe('validateBlueprint', () => {
    for (const scenario of testScenarios) {
        it(`should ${scenario.shouldPass ? 'pass for' : 'reject'} ${scenario.name}`, () => {
            try {
                validateBlueprint(scenario.blueprint);
                const result = 'passed';
                expect(scenario.shouldPass ? true : false).toBe(result !== 'passed');
            } catch (err) {
                expect(scenario.shouldPass ? true : false).toBe(false);
            }
        });
    }
});

describe('sanitizeBlueprint', () => {
    it('should fill missing fields with defaults', () => {
        const broken = {
            global_aesthetic: {},
            chronological_shots: [{}],
        };

        const sanitized = sanitizeBlueprint(broken);

        expect(sanitized.global_aesthetic.art_style).toBe('unknown');
        expect(sanitized.global_aesthetic.color_grading).toBe('unknown');
        expect(sanitized.chronological_shots[0].camera_direction).toBe('static camera');
    });
});

describe('validateVideoMetadata', () => {
    it('should return true for valid metadata', () => {
        const valid = {
            filename: 'video.mp4',
            duration_seconds: 10,
            width: 1920,
            height: 1080,
        };
        expect(validateVideoMetadata(valid)).toBe(true);
    });

    it('should return false for missing fields', () => {
        const invalid = {
            filename: 'video.mp4',
        };
        expect(validateVideoMetadata(invalid)).toBe(false);
    });
});