import { sanitizeBlueprint } from './validation.js';
import { compilePrompts } from '../src/compile.js';

export class FallbackMode {
    constructor() {
        this.enabled = false;
        this.reason = null;
    }

    activate(reason) {
        this.enabled = true;
        this.reason = reason;
    }

    isActive() {
        return this.enabled;
    }

    getReason() {
        return this.reason;
    }
}

export function buildFallbackBlueprint(step1Data) {
    const metadata = step1Data?.video_metadata || {};
    const audio = step1Data?.audio_data || {};
    const extraction = step1Data?.extraction || {};

    const duration = metadata.duration_seconds || 10;
    const aspectRatio = metadata.aspect_ratio || '16:9';
    const fps = metadata.fps || 30;

    let style = 'cinematic';
    if (fps < 24) style = 'low-fi recording';
    if (extraction.motion_signal_level === 'high') style = 'dynamic action';
    if (extraction.motion_signal_level === 'low') style = 'static scene';

    let colorGrade = 'natural color';
    if (audio.transcript && audio.transcript.length > 100) colorGrade = 'documentary style';

    let lighting = 'natural lighting';
    const dims = metadata.width && metadata.height;
    if (dims) {
        const brightness = (metadata.width * metadata.height) / (1920 * 1080);
        if (brightness > 1.2) lighting = 'bright ambient lighting';
        if (brightness < 0.8) lighting = 'low-key moody lighting';
    }

    const shotCount = Math.max(1, Math.ceil(duration / 5));

    const shots = [];
    for (let i = 0; i < shotCount; i++) {
        const shotDuration = Math.min(5, duration - (i * 5));
        if (shotDuration <= 0) break;

        shots.push({
            shot_index: i,
            duration_seconds: shotDuration,
            camera_direction: i === 0 ? 'static establishing shot' : 'medium shot',
            framing_type: i === 0 ? 'wide shot' : 'medium shot',
            action_and_motion: audio.transcript 
                ? `Dialogue: "${audio.transcript.slice(0, 100)}..."` 
                : `Scene content based on ${fps}fps motion analysis`,
            environment_context: `Video dimensions: ${metadata.dimensions || 'unknown'}, codec: ${metadata.codec || 'unknown'}`,
            negative_elements: [
                'artifacts',
                'compression noise',
                'wrong aspect ratio',
            ],
        });
    }

    return {
        global_aesthetic: {
            art_style: style,
            color_grading: colorGrade,
            lighting_setup: lighting,
        },
        chronological_shots: shots,
        _fallback_metadata: {
            source: 'text-only-fallback',
            reason: 'Gemini analysis unavailable',
            based_on: {
                duration_seconds: duration,
                dimensions: metadata.dimensions,
                fps: fps,
                codec: metadata.codec,
                aspect_ratio: aspectRatio,
                motion_signal_level: extraction.motion_signal_level,
                has_audio: audio.has_audio,
                transcript_available: !!audio.transcript,
            },
        },
    };
}

export function compileFallbackPrompts(blueprint, step1Data) {
    try {
        const metadata = step1Data?.video_metadata || {};
        return compilePrompts(blueprint, metadata);
    } catch (err) {
        console.warn('Fallback prompt compilation failed:', err.message);
        return {};
    }
}

export function logFallbackUsage(fallback, stepName, error) {
    console.log('\n═══════════════════════════════════════════');
    console.log('  ⚠️  FALLBACK MODE ACTIVE');
    console.log('═══════════════════════════════════════════');
    console.log(`  Step: ${stepName}`);
    console.log(`  Reason: ${fallback.getReason()}`);
    console.log(`  Error: ${error?.message || 'unknown'}`);
    console.log('───────────────────────────────────────────');
    console.log('  Fallback generates approximate results');
    console.log('  using local metadata only (no AI analysis).');
    console.log('  For best quality, fix the underlying issue.');
    console.log('═══════════════════════════════════════════\n');
}