function formatText(output) {
    const meta = output.video_metadata || {};
    const blueprint = output.blueprint || {};
    const prompts = output.prompts || {};
    const aesthetic = blueprint.global_aesthetic || {};
    const shots = blueprint.chronological_shots || [];

    const lines = [];

    lines.push('═'.repeat(60));
    lines.push('  VideoReverse — Video Recreation Guide');
    lines.push('═'.repeat(60));
    lines.push('');
    lines.push(`Video: ${meta.filename || 'Unknown'}`);
    lines.push(`Duration: ${meta.duration_seconds || '?'}s`);
    lines.push(`Resolution: ${meta.dimensions || '?'} (${meta.aspect_ratio || '?'})`);
    lines.push(`FPS: ${meta.fps || '?'}`);
    lines.push(``);
    lines.push(`Overall Style: ${aesthetic.art_style || 'N/A'}`);
    lines.push(`Lighting: ${aesthetic.lighting_setup || 'N/A'}`);
    lines.push(`Color Grading: ${aesthetic.color_grading || 'N/A'}`);
    lines.push('');
    lines.push('─'.repeat(60));
    lines.push('  Scene Breakdown');
    lines.push('─'.repeat(60));
    lines.push('');

    for (const shot of shots) {
        lines.push(`Shot ${shot.shot_index + 1} (${shot.duration_seconds}s)`);
        lines.push(`  Camera: ${shot.camera_direction || 'N/A'}`);
        lines.push(`  Framing: ${shot.framing_type || 'N/A'}`);
        lines.push(`  Action: ${shot.action_and_motion || 'N/A'}`);
        lines.push(`  Setting: ${shot.environment_context || 'N/A'}`);
        if (shot.negative_elements?.length) {
            lines.push(`  Avoid: ${shot.negative_elements.join(', ')}`);
        }
        lines.push('');
    }

    lines.push('═'.repeat(60));
    lines.push('  Ready-to-Use Prompts by Model');
    lines.push('═'.repeat(60));

    for (const [modelKey, modelData] of Object.entries(prompts)) {
        lines.push('');
        lines.push('─'.repeat(60));
        lines.push(`  ${modelData.label}`);
        lines.push('─'.repeat(60));
        lines.push('');

        for (const s of modelData.shots) {
            if (modelData.shots.length > 1) {
                lines.push(`Shot ${s.shot_index + 1} (${s.duration_seconds}s, ${s.aspect_ratio}):`);
                lines.push('');
            }
            lines.push(s.prompt);
            if (s.negative_prompt) {
                lines.push('');
                lines.push(`Negative: ${s.negative_prompt}`);
            }
            lines.push('');
        }
    }

    lines.push('═'.repeat(60));
    lines.push('  How to Use');
    lines.push('═'.repeat(60));
    lines.push('');
    lines.push('1. Pick a model section above (e.g., Runway Gen-4.5, Google Veo 3.1)');
    lines.push('2. Copy the prompt text for each shot');
    lines.push('3. Paste it into your chosen video AI generator');
    lines.push('4. If the model supports negative prompts, copy the "Negative:" line too');
    lines.push('5. Generate each shot separately, then combine them in a video editor');
    lines.push('');

    return lines.join('\n');
}

export { formatText };
