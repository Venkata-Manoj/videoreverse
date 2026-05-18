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

function applyEnhancementRules(prompt, modelConfig) {
    const rules = modelConfig.enhancement_rules;
    if (!rules) return prompt;

    let enhanced = prompt;
    const guidelines = rules.prompt_guidelines || {};

    // Inject model-specific keywords that improve output quality
    const keywords = rules.keyword_injection || {};
    const keywordPhrases = [];

    for (const [category, words] of Object.entries(keywords)) {
        if (Array.isArray(words)) {
            keywordPhrases.push(...words.filter(w => w && w.length > 0));
        }
    }

    // Add relevant keywords to the prompt if they complement existing content
    if (keywordPhrases.length > 0) {
        const lowerPrompt = enhanced.toLowerCase();
        const relevantKeywords = keywordPhrases.filter(kw =>
            !lowerPrompt.includes(kw.toLowerCase()) &&
            !lowerPrompt.includes(kw.toLowerCase().split(' ')[0])
        );

        if (relevantKeywords.length > 0) {
            const injectCount = Math.min(relevantKeywords.length, 2);
            const toInject = relevantKeywords.slice(0, injectCount).join(', ');

            if (guidelines.emphasize_comma_format) {
                enhanced = `${enhanced}, ${toInject}`;
            } else if (guidelines.emphasize_physics || guidelines.emphasize_environment) {
                enhanced = `${enhanced}. ${toInject}.`;
            } else if (guidelines.emphasize_motion || guidelines.emphasize_atmosphere) {
                enhanced = `${enhanced}. ${toInject}.`;
            } else if (guidelines.emphasize_temporal_flow) {
                enhanced = `${enhanced}. ${toInject}.`;
            } else if (guidelines.emphasize_style || guidelines.emphasize_animation) {
                enhanced = `${enhanced}. ${toInject}.`;
            } else if (guidelines.emphasize_realism || guidelines.emphasize_quality) {
                enhanced = `${enhanced}. ${toInject}.`;
            } else {
                enhanced = `${enhanced}. ${toInject}.`;
            }
        }
    }

    // Remove discouraged adjectives
    if (guidelines.avoid_adjectives) {
        for (const adj of guidelines.avoid_adjectives) {
            enhanced = enhanced.replace(new RegExp(`\\b${adj}\\b`, 'gi'), '');
        }
        enhanced = enhanced.replace(/\s{2,}/g, ' ').trim();
    }

    // Enforce max length by truncating at sentence boundary
    if (guidelines.max_length && enhanced.length > guidelines.max_length) {
        const truncated = enhanced.slice(0, guidelines.max_length);
        const lastSentenceEnd = Math.max(
            truncated.lastIndexOf('. '),
            truncated.lastIndexOf('! '),
            truncated.lastIndexOf('? ')
        );
        enhanced = lastSentenceEnd > guidelines.max_length * 0.6
            ? truncated.slice(0, lastSentenceEnd + 1)
            : truncated;
    }

    // Clean up trailing punctuation
    enhanced = enhanced.replace(/[\s.,]+$/, '').trim();

    return enhanced;
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

            let prompt = fillTemplate(modelConfig.template, vars);

            // Apply model-specific enhancement rules
            prompt = applyEnhancementRules(prompt, modelConfig);

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
