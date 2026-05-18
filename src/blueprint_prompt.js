const BLUEPRINT_SYSTEM_PROMPT = `You are an expert Director, Cinematographer, and Video Analyst. Your job is to deconstruct any video — regardless of genre, quality, or format — into a precise production blueprint that could be used to recreate it from scratch.

Analyze the uploaded video and output a structured JSON blueprint. Handle ALL video types:
- Live-action (films, commercials, vlogs, documentaries, news broadcasts)
- Animation (2D anime, 3D CGI, stop-motion, motion graphics, whiteboard)
- Screen recordings (tutorials, gameplay, software demos, presentations)
- Aerial/drone footage
- Social media content (TikTok, Reels, Shorts — vertical format)
- Music videos, concert footage, live performances
- Surveillance, bodycam, dashcam footage
- Product showcases, unboxing videos
- Educational content, lectures, webinars

For each shot, describe exactly what happens with enough detail that another creator could reproduce it. Include camera movements, subject actions, lighting, environment, and any on-screen text or graphics.`;

const BLUEPRINT_SCHEMA = {
    type: 'OBJECT',
    properties: {
        global_aesthetic: {
            type: 'OBJECT',
            properties: {
                art_style: { type: 'STRING', description: 'Overall visual style (e.g., photorealistic CGI, live-action documentary, 2D anime, stop-motion, screen recording, drone aerial, vlog handheld)' },
                color_grading: { type: 'STRING', description: 'Color palette and grading approach (e.g., warm golden hour, cool blue tones, high-contrast neon, natural daylight, desaturated moody)' },
                lighting_setup: { type: 'STRING', description: 'Lighting configuration (e.g., soft diffused studio lights, harsh direct sunlight, neon-lit night scene, natural window light, fluorescent office lighting)' },
            },
            required: ['art_style', 'color_grading', 'lighting_setup'],
        },
        chronological_shots: {
            type: 'ARRAY',
            description: 'Every distinct shot or scene change in the video, in chronological order. Include even brief cuts, transitions, and title cards.',
            items: {
                type: 'OBJECT',
                properties: {
                    shot_index: { type: 'INTEGER', description: 'Zero-based sequential index' },
                    duration_seconds: { type: 'NUMBER', format: 'float', description: 'Approximate duration of this shot in seconds' },
                    camera_direction: { type: 'STRING', description: 'Camera movement and lens behavior (e.g., static tripod, slow push-in, handheld shake, smooth gimbal pan, drone orbit, zoom rack focus, whip pan, tilt down)' },
                    framing_type: { type: 'STRING', description: 'Shot framing (e.g., extreme wide establishing, wide, medium wide, medium, medium close-up, close-up, extreme close-up, over-the-shoulder, point-of-view, top-down bird\'s-eye, low-angle hero, dutch angle)' },
                    action_and_motion: { type: 'STRING', description: 'What happens in this shot — subject actions, object movements, physics, interactions, emotional expressions, text animations, UI interactions. Be specific and detailed enough to recreate the exact visual.' },
                    environment_context: { type: 'STRING', description: 'The setting, background, and spatial context. Include surfaces, architecture, weather, time of day, crowd density, interior vs exterior, and any visible text or branding.' },
                    negative_elements: {
                        type: 'ARRAY',
                        description: 'Visual elements that should NOT appear or that are absent in this shot (e.g., no people in background, no text overlays, no watermarks, no lens flare, no motion blur)',
                        items: { type: 'STRING' },
                    },
                },
                required: ['shot_index', 'duration_seconds', 'camera_direction', 'framing_type', 'action_and_motion', 'environment_context', 'negative_elements'],
            },
        },
    },
    required: ['global_aesthetic', 'chronological_shots'],
};

export { BLUEPRINT_SYSTEM_PROMPT, BLUEPRINT_SCHEMA };
