import { GoogleGenAI } from '@google/genai';
import * as fs from 'fs';
import * as path from 'path';
import { BLUEPRINT_SYSTEM_PROMPT, BLUEPRINT_SCHEMA } from './blueprint_prompt.js';
import { getRoot } from './path-resolver.js';

function loadEnvKey() {
    const envPath = path.join(getRoot(), '.env');
    try {
        const raw = fs.readFileSync(envPath, 'utf-8');
        for (const line of raw.split('\n')) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) continue;
            const eq = trimmed.indexOf('=');
            if (eq === -1) continue;
            const key = trimmed.slice(0, eq).trim();
            const val = trimmed.slice(eq + 1).trim();
            if (key === 'GEMINI_API_KEY') return val;
        }
    } catch {}
    return process.env.GEMINI_API_KEY || null;
}

const apiKey = loadEnvKey();
if (!apiKey) throw new Error('GEMINI_API_KEY not found in .env or environment');
const ai = new GoogleGenAI({ apiKey });

async function buildBlueprint(videoPath, step1Data, options = {}) {
    console.log(`🧠 VideoReverse: Step 3 — Blueprint Synthesis (Frame-Aware)`);
    console.log(`📡 Uploading video to Gemini File API...`);

    const normalized = videoPath;
    if (!fs.existsSync(normalized)) {
        throw new Error(`Video file not found: ${normalized}`);
    }

    let file;
    try {
        file = await ai.files.upload({
            file: normalized,
            config: { mimeType: 'video/mp4' },
        });
        console.log(`   → Uploaded: ${file.name} (${(file.sizeBytes / 1024 / 1024).toFixed(1)} MB)`);

        console.log(`   → Waiting for file processing...`);
        let processing = false;
        for (let i = 0; i < 60; i++) {
            await new Promise(r => setTimeout(r, 1000));
            const status = await ai.files.get({ name: file.name });
            if (status.state === 'ACTIVE') {
                console.log(`   → File ready (${i + 1}s)`);
                processing = true;
                break;
            }
            if (status.state === 'FAILED') {
                throw new Error(`File processing failed: ${status.error?.message || 'unknown error'}`);
            }
        }
        if (!processing) {
            throw new Error('File processing timed out after 60s');
        }

        const metadata = step1Data?.video_metadata || {};
        const audio = step1Data?.audio_data || {};
        const extraction = step1Data?.extraction || {};
        const timelineFrames = step1Data?.timeline_frames || [];

        const frameContext = buildFrameContext(timelineFrames);

        const audioInfo = audio.mood?.mood 
            ? `Audio mood: ${audio.mood.mood}`
            : `Audio: ${audio.has_audio ? 'Yes' : 'No'}`;
        
        const userPrompt = `Analyze this video and produce a complete production blueprint with frame-aware analysis.

Technical context from local analysis:
- Duration: ${metadata.duration_seconds || 'unknown'}s
- Resolution: ${metadata.dimensions || 'unknown'} (${metadata.aspect_ratio || 'unknown'})
- FPS: ${metadata.fps || 0}
- Codec: ${metadata.codec || 'unknown'}
- Motion level: ${extraction.motion_signal_level || 'unknown'}
${frameContext}
- ${audioInfo}${audio.transcript ? ` — Transcript: "${audio.transcript}"` : ''}
${audio.mood?.indicators ? `- Audio profile: ${Object.entries(audio.mood.indicators).filter(([,v]) => v).map(([k]) => k).join(', ') || 'none'}` : ''}

Break the video into chronological shots. For each shot, describe:
1. How long it lasts (use start_time_seconds and end_time_seconds)
2. What the camera is doing (static, panning, zooming, handheld, etc.)
3. How the scene is framed (wide, close-up, etc.)
4. Exactly what happens — actions, movements, expressions, physics
5. The environment and background details
6. What is NOT present (negative elements)

CRITICAL - Frame Reference Requirements:
For EACH shot, you MUST include a frame_references array that:
- Lists which timeline frames (by index) informed this shot
- Correlates shot times with frame timestamps
- Indicates frame relevance (key_frame, transition_frame, supporting)
- Shows which frames triggered the shot boundary

Also identify the overall art style, color grading, and lighting setup.`;

        let systemInstruction = BLUEPRINT_SYSTEM_PROMPT;
        
        if (audio.mood?.mood) {
            systemInstruction += `\n\nAudio mood context: "${audio.mood.mood}". `;
            if (audio.mood.mood === 'dynamic') {
                systemInstruction += 'Expect high-energy content with music and action.';
            } else if (audio.mood.mood === 'contemplative') {
                systemInstruction += 'Expect slow-paced content with ambient sound.';
            } else if (audio.mood.mood === 'documentary') {
                systemInstruction += 'Expect speech-heavy content with dialogue.';
            }
        }
        
        if (extraction.motion_signal_level === 'high') {
            systemInstruction += ' High motion content - emphasize dynamic camera work.';
        } else if (extraction.motion_signal_level === 'low') {
            systemInstruction += ' Low motion content - emphasize static compositions.';
        }

        systemInstruction += `\n\nFrame-aware analysis enabled. Total frames in timeline: ${timelineFrames.length}.
Each shot MUST include frame_references correlating to the timeline.`;

        console.log(`🔍 Sending to Gemini for frame-aware multimodal analysis...`);
        console.log(`   → Frame context: ${timelineFrames.length} frames available`);

        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: [
                { text: userPrompt },
                { fileData: { fileUri: file.uri, mimeType: 'video/mp4' } },
            ],
            config: {
                responseMimeType: 'application/json',
                responseSchema: BLUEPRINT_SCHEMA,
                systemInstruction: systemInstruction,
            },
        });

        const blueprint = JSON.parse(response.text);

        if (!blueprint.global_aesthetic || !Array.isArray(blueprint.chronological_shots)) {
            throw new Error('Blueprint missing required fields');
        }

        if (audio.mood?.mood) {
            blueprint.global_aesthetic._audio_mood = audio.mood.mood;
        }

        blueprint._metadata = {
            total_frames_analyzed: timelineFrames.length,
            shots_with_frame_traceability: blueprint.chronological_shots.filter(s => 
                s.frame_references && s.frame_references.length > 0
            ).length,
            analysis_timestamp: new Date().toISOString(),
            frame_timeline: timelineFrames.map(f => ({
                index: f.index,
                timestamp_seconds: f.timestamp_seconds,
                motion_level: f.motion_level,
            })),
        };

        console.log(`✅ Frame-aware blueprint generated:`);
        console.log(`   → ${blueprint.chronological_shots.length} shots identified`);
        console.log(`   → ${blueprint._metadata.shots_with_frame_traceability} shots with frame traceability`);

        return blueprint;

    } finally {
        if (file) {
            try {
                await ai.files.delete({ name: file.name });
                console.log(`   → Cleaned up uploaded file from Gemini`);
            } catch (e) {
                console.log(`   → Cleanup warning: ${e.message}`);
            }
        }
    }
}

function buildFrameContext(timelineFrames) {
    if (!timelineFrames || timelineFrames.length === 0) {
        return '- Frames extracted: 0';
    }

    const lines = ['- Frame timeline (peepshow extracted keyframes):'];
    
    lines.push(`  Total frames: ${timelineFrames.length}`);

    const highMotionFrames = timelineFrames.filter(f => f.motion_level === 'high');
    const lowMotionFrames = timelineFrames.filter(f => f.motion_level === 'low');

    if (highMotionFrames.length > 0) {
        const indices = highMotionFrames.slice(0, 5).map(f => f.index).join(', ');
        const more = highMotionFrames.length > 5 ? ` (+${highMotionFrames.length - 5} more)` : '';
        lines.push(`  High motion frames: [${indices}]${more}`);
    }

    if (lowMotionFrames.length > 0) {
        const indices = lowMotionFrames.slice(0, 5).map(f => f.index).join(', ');
        const more = lowMotionFrames.length > 5 ? ` (+${lowMotionFrames.length - 5} more)` : '';
        lines.push(`  Low motion frames: [${indices}]${more}`);
    }

    lines.push('');
    lines.push('  Frame details (format: [index] @timestamp_s - motion):');
    
    for (const frame of timelineFrames.slice(0, 20)) {
        const ts = frame.timestamp_seconds?.toFixed(2) || '0.00';
        const motion = frame.motion_level || 'medium';
        lines.push(`    [${frame.index}] @ ${ts}s - ${motion}`);
    }

    if (timelineFrames.length > 20) {
        lines.push(`    ... and ${timelineFrames.length - 20} more frames`);
    }

    return lines.join('\n');
}

export { buildBlueprint };