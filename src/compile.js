import * as fs from 'fs';
import { getConfigPath } from './path-resolver.js';

function loadTemplates() {
    const tplPath = getConfigPath('prompt_templates.json');
    if (!fs.existsSync(tplPath)) {
        throw new Error(`prompt_templates.json not found at ${tplPath}`);
    }
    return JSON.parse(fs.readFileSync(tplPath, 'utf-8'));
}

function resolveAspectRatio(width, height) {
    if (!width || !height) return '16:9';
    const gcd = (a, b) => (b === 0 ? a : gcd(b, a % b));
    const d = gcd(width, height);
    const ratio = `${width / d}:${height / d}`;
    const common = { '16:9': '16:9', '9:16': '9:16', '1:1': '1:1', '4:3': '4:3', '3:4': '3:4' };
    return common[ratio] || '16:9';
}

function fillTemplate(template, vars) {
    let result = template;
    for (const [key, value] of Object.entries(vars)) {
        result = result.replace(new RegExp(`\\{${key}\\}`, 'g'), value || '');
    }
    result = result.replace(/\s{2,}/g, ' ').replace(/\.\s*\./g, '.').trim();
    return result;
}

function compilePrompts(blueprint, videoMetadata, filterModels = null) {
    console.log(`⚙️  VideoReverse: Step 6 — Prompt Compilation`);

    const templates = loadTemplates();
    const shots = blueprint.chronological_shots || [];
    const aesthetic = blueprint.global_aesthetic || {};
    const aspectRatio = resolveAspectRatio(videoMetadata?.width, videoMetadata?.height);

    if (shots.length === 0) {
        throw new Error('No chronological shots in blueprint');
    }

    const allOutputs = {};

    for (const [modelKey, modelConfig] of Object.entries(templates)) {
        if (filterModels && !filterModels.includes(modelKey)) {
            continue;
        }

        const modelPrompts = [];

        for (const shot of shots) {
            const duration = Math.min(shot.duration_seconds || 5, modelConfig.max_duration || 10);
            const negativeText = (shot.negative_elements || []).join(', ');

            const vars = {
                camera: shot.camera_direction || 'static camera',
                framing: shot.framing_type || 'medium shot',
                style: aesthetic.art_style || 'cinematic photorealistic',
                action: shot.action_and_motion || '',
                environment: shot.environment_context || 'neutral background',
                lighting: aesthetic.lighting_setup || 'natural lighting',
                color_grading: aesthetic.color_grading || 'natural color',
                duration: duration.toFixed(1),
                negative: modelConfig.supports_negative && negativeText
                    ? (modelConfig.negative_placeholder || '').replace('{negative}', negativeText)
                    : '',
                aspect_ratio: modelConfig.aspect_ratio_support.includes(aspectRatio) ? aspectRatio : modelConfig.aspect_ratio_support[0],
            };

            const prompt = fillTemplate(modelConfig.template, vars);

            modelPrompts.push({
                shot_index: shot.shot_index ?? modelPrompts.length,
                duration_seconds: duration,
                aspect_ratio: vars.aspect_ratio,
                prompt,
                ...(modelConfig.supports_negative && negativeText ? { negative_prompt: negativeText } : {}),
            });
        }

        allOutputs[modelKey] = {
            label: modelConfig.label,
            max_duration: modelConfig.max_duration,
            aspect_ratio: resolveAspectRatio(videoMetadata?.width, videoMetadata?.height),
            shots: modelPrompts,
        };

        console.log(`   → ${modelConfig.label}: ${modelPrompts.length} prompts compiled`);
    }

    return allOutputs;
}

export { compilePrompts };