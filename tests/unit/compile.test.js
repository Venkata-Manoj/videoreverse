import { compilePrompts } from '../../src/compile.js';
import { describe, it, expect } from './test-framework.js';

const mockBlueprint = {
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
            action_and_motion: 'person walking',
            environment_context: 'beach',
            negative_elements: ['blur', 'noise'],
        },
        {
            shot_index: 1,
            duration_seconds: 3,
            camera_direction: 'tracking',
            framing_type: 'close-up',
            action_and_motion: 'smile',
            environment_context: 'studio',
            negative_elements: [],
        },
    ],
};

const mockMetadata = {
    width: 1920,
    height: 1080,
};

describe('compilePrompts', () => {
    it('should generate prompts for all models', () => {
        const prompts = compilePrompts(mockBlueprint, mockMetadata);

        expect(Object.keys(prompts).length).toBeGreaterThan(0);
        expect(prompts.runway_gen4_5).toBeDefined();
        expect(prompts.google_veo3_1).toBeDefined();
    });

    it('should include shot information in prompts', () => {
        const prompts = compilePrompts(mockBlueprint, mockMetadata);
        const runway = prompts.runway_gen4_5;

        expect(runway.shots.length).toBe(2);
        expect(runway.shots[0].shot_index).toBe(0);
        expect(runway.shots[0].duration_seconds).toBe(5);
    });

    it('should filter models when filterModels provided', () => {
        const prompts = compilePrompts(mockBlueprint, mockMetadata, ['runway_gen4_5']);

        expect(Object.keys(prompts).length).toBe(1);
        expect(prompts.runway_gen4_5).toBeDefined();
        expect(prompts.google_veo3_1).toBeUndefined();
    });

    it('should handle empty negative_elements', () => {
        const noNegatives = {
            ...mockBlueprint,
            chronological_shots: [
                {
                    ...mockBlueprint.chronological_shots[0],
                    negative_elements: [],
                },
            ],
        };

        const prompts = compilePrompts(noNegatives, mockMetadata);
        expect(prompts.runway_gen4_5).toBeDefined();
    });
});