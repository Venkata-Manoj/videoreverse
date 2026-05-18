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
    console.log(`🧠 VideoReverse: Step 3 — Blueprint Synthesis`);
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

        const audioInfo = audio.mood?.mood 
            ? `Audio mood: ${audio.mood.mood}`
            : `Audio: ${audio.has_audio ? 'Yes' : 'No'}`;
        
        const userPrompt = `Analyze this video and produce a complete production blueprint.

Technical context from local analysis:
- Duration: ${metadata.duration_seconds || 'unknown'}s
- Resolution: ${metadata.dimensions || 'unknown'} (${metadata.aspect_ratio || 'unknown'})
- FPS: ${metadata.fps || 0}
- Codec: ${metadata.codec || 'unknown'}
- Motion level: ${extraction.motion_signal_level || 'unknown'}
- Frames extracted: ${extraction.frames_emitted || 0}
- ${audioInfo}${audio.transcript ? ` — Transcript: "${audio.transcript}"` : ''}
${audio.mood?.indicators ? `- Audio profile: ${Object.entries(audio.mood.indicators).filter(([,v]) => v).map(([k]) => k).join(', ') || 'none'}` : ''}

Break the video into chronological shots. For each shot, describe:
1. How long it lasts
2. What the camera is doing (static, panning, zooming, handheld, etc.)
3. How the scene is framed (wide, close-up, etc.)
4. Exactly what happens — actions, movements, expressions, physics
5. The environment and background details
6. What is NOT present (negative elements)

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

        console.log(`🔍 Sending to Gemini for multimodal analysis...`);

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

        console.log(`✅ Blueprint generated: ${blueprint.chronological_shots.length} shots identified`);
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

export { buildBlueprint };