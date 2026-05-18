export class BlueprintValidationError extends Error {
    constructor(message, field = null) {
        super(message);
        this.name = 'BlueprintValidationError';
        this.field = field;
    }
}

export function validateBlueprint(blueprint) {
    const errors = [];

    if (!blueprint) {
        throw new BlueprintValidationError('Blueprint is null or undefined');
    }

    if (typeof blueprint !== 'object') {
        throw new BlueprintValidationError(`Blueprint must be an object, got ${typeof blueprint}`);
    }

    if (!blueprint.global_aesthetic || typeof blueprint.global_aesthetic !== 'object') {
        throw new BlueprintValidationError('Missing or invalid global_aesthetic object', 'global_aesthetic');
    }

    const aesthetic = blueprint.global_aesthetic;
    const requiredAestheticFields = ['art_style', 'color_grading', 'lighting_setup'];

    for (const field of requiredAestheticFields) {
        if (!aesthetic[field] || typeof aesthetic[field] !== 'string') {
            errors.push(`global_aesthetic.${field} must be a non-empty string`);
        }
    }

    if (!Array.isArray(blueprint.chronological_shots)) {
        throw new BlueprintValidationError('Missing or invalid chronological_shots array', 'chronological_shots');
    }

    if (blueprint.chronological_shots.length === 0) {
        throw new BlueprintValidationError('chronological_shots cannot be empty', 'chronological_shots');
    }

    const requiredShotFields = [
        'shot_index', 'duration_seconds', 'camera_direction',
        'framing_type', 'action_and_motion', 'environment_context', 'negative_elements'
    ];

    for (let i = 0; i < blueprint.chronological_shots.length; i++) {
        const shot = blueprint.chronological_shots[i];

        if (!shot || typeof shot !== 'object') {
            errors.push(`Shot ${i}: must be an object`);
            continue;
        }

        for (const field of requiredShotFields) {
            if (shot[field] === undefined || shot[field] === null) {
                errors.push(`Shot ${i}: missing required field "${field}"`);
            }
        }

        if (typeof shot.shot_index !== 'number' || shot.shot_index < 0) {
            errors.push(`Shot ${i}: shot_index must be a non-negative number`);
        }

        if (typeof shot.duration_seconds !== 'number' || shot.duration_seconds <= 0) {
            errors.push(`Shot ${i}: duration_seconds must be a positive number`);
        }

        for (const field of ['camera_direction', 'framing_type', 'action_and_motion', 'environment_context']) {
            if (typeof shot[field] !== 'string') {
                errors.push(`Shot ${i}: ${field} must be a string`);
            }
        }

        if (!Array.isArray(shot.negative_elements)) {
            errors.push(`Shot ${i}: negative_elements must be an array`);
        }
    }

    if (errors.length > 0) {
        throw new BlueprintValidationError(`Validation failed:\n  - ${errors.join('\n  - ')}`);
    }

    return true;
}

export function validateVideoMetadata(metadata) {
    if (!metadata) return false;

    const required = ['filename', 'duration_seconds', 'width', 'height'];
    for (const field of required) {
        if (metadata[field] === undefined || metadata[field] === null) {
            return false;
        }
    }

    return metadata.duration_seconds > 0 && metadata.width > 0 && metadata.height > 0;
}

export function sanitizeBlueprint(blueprint) {
    if (!blueprint) return null;

    const sanitized = {
        global_aesthetic: {
            art_style: blueprint.global_aesthetic?.art_style || 'unknown',
            color_grading: blueprint.global_aesthetic?.color_grading || 'unknown',
            lighting_setup: blueprint.global_aesthetic?.lighting_setup || 'unknown',
        },
        chronological_shots: []
    };

    for (const shot of (blueprint.chronological_shots || [])) {
        sanitized.chronological_shots.push({
            shot_index: typeof shot.shot_index === 'number' ? shot.shot_index : 0,
            duration_seconds: typeof shot.duration_seconds === 'number' && shot.duration_seconds > 0 ? shot.duration_seconds : 5,
            camera_direction: shot.camera_direction || 'static camera',
            framing_type: shot.framing_type || 'medium shot',
            action_and_motion: shot.action_and_motion || 'no action',
            environment_context: shot.environment_context || 'unknown environment',
            negative_elements: Array.isArray(shot.negative_elements) ? shot.negative_elements : [],
        });
    }

    return sanitized;
}