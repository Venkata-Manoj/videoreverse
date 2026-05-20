def format_text(output):
    meta = output.get('video_metadata', {})
    blueprint = output.get('blueprint', {})
    prompts = output.get('prompts', {})
    aesthetic = blueprint.get('global_aesthetic', {})
    shots = blueprint.get('chronological_shots', [])

    lines = []

    lines.append('═' * 60)
    lines.append('  VideoReverse — Video Recreation Guide')
    lines.append('═' * 60)
    lines.append('')
    lines.append(f'Video: {meta.get("filename", "Unknown")}')
    lines.append(f'Duration: {meta.get("duration_seconds", "?")}s')
    lines.append(f'Resolution: {meta.get("dimensions", "?")} ({meta.get("aspect_ratio", "?")})')
    lines.append(f'FPS: {meta.get("fps", "?")}')
    lines.append('')
    lines.append(f'Overall Style: {aesthetic.get("art_style", "N/A")}')
    lines.append(f'Lighting: {aesthetic.get("lighting_setup", "N/A")}')
    lines.append(f'Color Grading: {aesthetic.get("color_grading", "N/A")}')
    lines.append('')
    lines.append('─' * 60)
    lines.append('  Scene Breakdown')
    lines.append('─' * 60)
    lines.append('')

    for shot in shots:
        lines.append(f'Shot {shot.get("shot_index", 0) + 1} ({shot.get("duration_seconds", "?")}s)')
        lines.append(f'  Camera: {shot.get("camera_direction", "N/A")}')
        lines.append(f'  Framing: {shot.get("framing_type", "N/A")}')
        lines.append(f'  Action: {shot.get("action_and_motion", "N/A")}')
        lines.append(f'  Setting: {shot.get("environment_context", "N/A")}')
        if shot.get('negative_elements'):
            lines.append(f'  Avoid: {", ".join(shot["negative_elements"])}')
        lines.append('')

    lines.append('═' * 60)
    lines.append('  Ready-to-Use Prompts by Model')
    lines.append('═' * 60)

    for model_key, model_data in prompts.items():
        lines.append('')
        lines.append('─' * 60)
        lines.append(f'  {model_data["label"]}')
        lines.append('─' * 60)
        lines.append('')

        for s in model_data.get('shots', []):
            if len(model_data.get('shots', [])) > 1:
                lines.append(f'Shot {s.get("shot_index", 0) + 1} ({s.get("duration_seconds", "?")}s, {s.get("aspect_ratio", "?")}):')
                lines.append('')
            lines.append(s['prompt'])
            if s.get('negative_prompt'):
                lines.append('')
                lines.append(f'Negative: {s["negative_prompt"]}')
            lines.append('')

    lines.append('═' * 60)
    lines.append('  How to Use')
    lines.append('═' * 60)
    lines.append('')
    lines.append('1. Pick a model section above (e.g., Runway Gen-4.5, Google Veo 3.1)')
    lines.append('2. Copy the prompt text for each shot')
    lines.append('3. Paste it into your chosen video AI generator')
    lines.append('4. If the model supports negative prompts, copy the "Negative:" line too')
    lines.append('5. Generate each shot separately, then combine them in a video editor')
    lines.append('')

    return '\n'.join(lines)
