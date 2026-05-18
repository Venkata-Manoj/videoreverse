import { execSync } from 'child_process';
import * as path from 'path';
import { fileURLToPath } from 'url';

function normalizePath(target) {
    if (typeof target !== 'string') return target;
    if (target.includes('://')) return target;
    const isWindowsPath = /^[a-zA-Z]:[\\/]/.test(target);
    if (isWindowsPath) {
        const drive = target[0].toLowerCase();
        const posixPath = target.slice(2).replace(/\\/g, '/').replace(/^\/+/, '');
        return `/mnt/${drive}/${posixPath}`;
    }
    if (/^\/mnt\/[a-z]\//i.test(target)) return target;
    return path.resolve(target);
}

function checkPeepshow() {
    try {
        const result = execSync('peepshow --help', { maxBuffer: 1024 * 1024, encoding: 'utf8' });
        return result.includes('peepshow');
    } catch {
        return false;
    }
}

async function ingestVideo(videoTarget) {
    console.log(`🚀 VideoReverse: Step 1 — Ingestion & Sampling`);
    const normalized = normalizePath(videoTarget);
    console.log(`🎥 Target: ${videoTarget}`);
    if (normalized !== videoTarget) console.log(`   → Resolved: ${normalized}`);
    console.log();

    const peepshowAvailable = checkPeepshow();
    if (!peepshowAvailable) {
        console.error(`❌ peepshow not found on PATH.`);
        console.error(`   Fix: npm i -g peepshow`);
        console.error(`   Requires Node.js 22+ (use nvm install 22)\n`);
        throw new Error('peepshow not found');
    }

    try {
        const escaped = normalized.replace(/"/g, '\\"');
        const command = `peepshow "${escaped}" --emit json --stats off`;
        
        const stdout = execSync(command, {
            maxBuffer: 1024 * 1024 * 10,
            encoding: 'utf8',
            shell: '/bin/bash',
        });

        const jsonStart = stdout.indexOf('{');
        const jsonEnd = stdout.lastIndexOf('}');
        if (jsonStart === -1 || jsonEnd === -1) {
            throw new Error('peepshow output contained no JSON payload');
        }
        const raw = JSON.parse(stdout.slice(jsonStart, jsonEnd + 1));

        const filename = normalized.includes('://')
            ? normalized.split('/').pop() || 'unknown'
            : path.basename(normalized);

        const hasAudio = !!(raw.audio?.path && !raw.audio.skippedReason);
        const audioMood = analyzeAudioMood(raw.audio);
        const timelineFrames = extractFrameMetadata(raw.frames, raw.video?.fps || 30);

        return {
            pipeline_step: '1_ingestion_and_sampling',
            video_metadata: {
                filename,
                source_path: normalized,
                duration_seconds: raw.video?.durationSeconds || 0,
                width: raw.video?.width || 0,
                height: raw.video?.height || 0,
                dimensions: `${raw.video?.width || 0}x${raw.video?.height || 0}`,
                aspect_ratio: computeAspectRatio(raw.video?.width, raw.video?.height),
                fps: raw.video?.fps || 0,
                codec: raw.video?.codec || 'unknown',
                container: raw.video?.container || 'unknown',
                bitrate_kbps: raw.video?.bitrateKbps || 0,
            },
            audio_data: {
                has_audio: hasAudio,
                audio_path: raw.audio?.path || null,
                transcript: raw.audio?.transcript?.text || '',
                transcript_segments: raw.audio?.transcript?.segments || [],
                audio_codec: raw.audio?.codec || null,
                silence_ratio: raw.audio?.silenceRatio ?? null,
                mood: audioMood,
            },
            extraction: {
                strategy: raw.extraction?.strategy || 'unknown',
                motion_signal_level: raw.extraction?.motionSignalLevel || 'unknown',
                frames_emitted: raw.extraction?.framesEmitted || 0,
                frames_deduped: raw.extraction?.framesDeduped || 0,
                elapsed_ms: raw.extraction?.elapsedMs || 0,
            },
            timeline_frames: timelineFrames,
            output_dir: raw.outputDir || null,
        };
    } catch (error) {
        console.error(`❌ Step 1 failed:`, error.message);
        throw error;
    }
}

function extractFrameMetadata(frames, fps) {
    if (!frames || !Array.isArray(frames)) return [];

    return frames.map((f, i) => {
        const estimatedTimestamp = fps > 0 ? i / fps : 0;

        let motionLevel = 'medium';
        if (f.bytes) {
            if (f.bytes < 30000) motionLevel = 'low';
            else if (f.bytes > 150000) motionLevel = 'high';
        }

        return {
            index: i,
            path: f.path,
            bytes: f.bytes || 0,
            timestamp_seconds: f.timestampSeconds || estimatedTimestamp,
            motion_level: f.motionLevel || motionLevel,
            frame_hash: f.hash || generateSimpleHash(f.path + i),
        };
    });
}

function generateSimpleHash(input) {
    let hash = 0;
    for (let i = 0; i < input.length; i++) {
        const char = input.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return Math.abs(hash).toString(16).padStart(8, '0');
}

function computeAspectRatio(w, h) {
    if (!w || !h) return 'unknown';
    const gcd = (a, b) => (b === 0 ? a : gcd(b, a % b));
    const d = gcd(w, h);
    return `${w / d}:${h / d}`;
}

function analyzeAudioMood(audio) {
    if (!audio) return null;

    const transcript = audio.transcript?.text || '';
    const silenceRatio = audio.silenceRatio ?? 0;
    const codec = audio.codec || '';

    const moodIndicators = {
        silence_dominant: silenceRatio > 0.5,
        transcript_heavy: transcript.length > 500,
        music_detected: codec.toLowerCase().includes('mp3') || codec.toLowerCase().includes('aac'),
        ambient: silenceRatio > 0.3 && transcript.length < 100,
    };

    let mood = 'neutral';

    if (moodIndicators.silence_dominant) mood = 'contemplative';
    if (moodIndicators.ambient) mood = 'atmospheric';
    if (moodIndicators.music_detected && silenceRatio < 0.2) mood = 'dynamic';
    if (moodIndicators.transcript_heavy) mood = 'documentary';

    const keywords = {
        tense: ['tension', 'fear', 'danger', 'alarm', 'worried'],
        emotional: ['love', 'happy', 'sad', 'cry', 'laugh', 'joy'],
        action: ['run', 'explode', 'crash', 'fight', 'chase', 'fast'],
        calm: ['quiet', 'peace', 'sleep', 'rest', 'slow', 'calm'],
    };

    const lowerTranscript = transcript.toLowerCase();
    for (const [m, words] of Object.entries(keywords)) {
        if (words.some(w => lowerTranscript.includes(w))) {
            mood = m;
            break;
        }
    }

    return {
        mood,
        indicators: moodIndicators,
        confidence: silenceRatio > 0 || transcript.length > 0 ? 'medium' : 'low',
    };
}

export { ingestVideo, normalizePath };