class BlueprintValidationError(Exception):
    def __init__(self, message, field=None):
        super().__init__(message)
        self.name = 'BlueprintValidationError'
        self.field = field


def validate_blueprint(blueprint):
    errors = []

    if not blueprint:
        raise BlueprintValidationError('Blueprint is null or undefined')

    if not isinstance(blueprint, dict):
        raise BlueprintValidationError(f'Blueprint must be an object, got {type(blueprint).__name__}')

    if not blueprint.get('global_aesthetic') or not isinstance(blueprint['global_aesthetic'], dict):
        raise BlueprintValidationError('Missing or invalid global_aesthetic object', 'global_aesthetic')

    aesthetic = blueprint['global_aesthetic']
    required_aesthetic_fields = ['art_style', 'color_grading', 'lighting_setup']

    for field in required_aesthetic_fields:
        if not aesthetic.get(field) or not isinstance(aesthetic[field], str):
            errors.append(f'global_aesthetic.{field} must be a non-empty string')

    if not isinstance(blueprint.get('chronological_shots'), list):
        raise BlueprintValidationError('Missing or invalid chronological_shots array', 'chronological_shots')

    if len(blueprint['chronological_shots']) == 0:
        raise BlueprintValidationError('chronological_shots cannot be empty', 'chronological_shots')

    required_shot_fields = [
        'shot_index', 'start_time_seconds', 'end_time_seconds', 'duration_seconds',
        'camera_direction', 'framing_type', 'action_and_motion', 'environment_context',
        'negative_elements', 'frame_references'
    ]

    for i, shot in enumerate(blueprint['chronological_shots']):
        if not shot or not isinstance(shot, dict):
            errors.append(f'Shot {i}: must be an object')
            continue

        for field in required_shot_fields:
            if shot.get(field) is None:
                errors.append(f'Shot {i}: missing required field "{field}"')

        if not isinstance(shot.get('shot_index'), (int, float)) or shot.get('shot_index', -1) < 0:
            errors.append(f'Shot {i}: shot_index must be a non-negative number')

        if not isinstance(shot.get('start_time_seconds'), (int, float)) or shot.get('start_time_seconds', -1) < 0:
            errors.append(f'Shot {i}: start_time_seconds must be a non-negative number')

        if not isinstance(shot.get('end_time_seconds'), (int, float)) or shot.get('end_time_seconds', -1) < 0:
            errors.append(f'Shot {i}: end_time_seconds must be a non-negative number')

        if isinstance(shot.get('start_time_seconds'), (int, float)) and isinstance(shot.get('end_time_seconds'), (int, float)):
            if shot['start_time_seconds'] >= shot['end_time_seconds']:
                errors.append(f'Shot {i}: start_time_seconds must be less than end_time_seconds')

        if not isinstance(shot.get('duration_seconds'), (int, float)) or shot.get('duration_seconds', 0) <= 0:
            errors.append(f'Shot {i}: duration_seconds must be a positive number')

        for field in ['camera_direction', 'framing_type', 'action_and_motion', 'environment_context']:
            if not isinstance(shot.get(field), str):
                errors.append(f'Shot {i}: {field} must be a string')

        if not isinstance(shot.get('negative_elements'), list):
            errors.append(f'Shot {i}: negative_elements must be an array')

        if not isinstance(shot.get('frame_references'), list):
            errors.append(f'Shot {i}: frame_references must be an array')
        else:
            for j, ref in enumerate(shot['frame_references']):
                if not isinstance(ref.get('frame_index'), (int, float)) or ref.get('frame_index', -1) < 0:
                    errors.append(f'Shot {i}: frame_references[{j}].frame_index must be a non-negative number')
                if not isinstance(ref.get('timestamp_seconds'), (int, float)):
                    errors.append(f'Shot {i}: frame_references[{j}].timestamp_seconds must be a number')

        if shot.get('shot_boundaries') is not None:
            if not isinstance(shot['shot_boundaries'], dict):
                errors.append(f'Shot {i}: shot_boundaries must be an object')
            else:
                if shot['shot_boundaries'].get('detected_by') and not isinstance(shot['shot_boundaries']['detected_by'], str):
                    errors.append(f'Shot {i}: shot_boundaries.detected_by must be a string')
                if shot['shot_boundaries'].get('confidence') and not isinstance(shot['shot_boundaries']['confidence'], str):
                    errors.append(f'Shot {i}: shot_boundaries.confidence must be a string')

    if errors:
        raise BlueprintValidationError('Validation failed:\n  - ' + '\n  - '.join(errors))

    return True


def validate_video_metadata(metadata):
    if not metadata:
        return False

    required = ['filename', 'duration_seconds', 'width', 'height']
    for field in required:
        if metadata.get(field) is None:
            return False

    return metadata['duration_seconds'] > 0 and metadata['width'] > 0 and metadata['height'] > 0


def sanitize_blueprint(blueprint):
    if not blueprint:
        return None

    aesthetic = blueprint.get('global_aesthetic') or {}
    sanitized = {
        'global_aesthetic': {
            'art_style': aesthetic.get('art_style') or 'unknown',
            'color_grading': aesthetic.get('color_grading') or 'unknown',
            'lighting_setup': aesthetic.get('lighting_setup') or 'unknown',
        },
        'chronological_shots': []
    }

    for shot in (blueprint.get('chronological_shots') or []):
        sanitized_shot = {
            'shot_index': shot.get('shot_index') if isinstance(shot.get('shot_index'), (int, float)) else 0,
            'start_time_seconds': shot.get('start_time_seconds') if isinstance(shot.get('start_time_seconds'), (int, float)) else 0,
            'end_time_seconds': shot.get('end_time_seconds') if isinstance(shot.get('end_time_seconds'), (int, float)) else 5,
            'duration_seconds': shot.get('duration_seconds') if isinstance(shot.get('duration_seconds'), (int, float)) and shot.get('duration_seconds', 0) > 0 else 5,
            'camera_direction': shot.get('camera_direction') or 'static camera',
            'framing_type': shot.get('framing_type') or 'medium shot',
            'action_and_motion': shot.get('action_and_motion') or 'no action',
            'environment_context': shot.get('environment_context') or 'unknown environment',
            'negative_elements': shot.get('negative_elements') if isinstance(shot.get('negative_elements'), list) else [],
            'frame_references': shot.get('frame_references') if isinstance(shot.get('frame_references'), list) else [],
        }

        if shot.get('shot_boundaries') and isinstance(shot['shot_boundaries'], dict):
            sanitized_shot['shot_boundaries'] = {
                'detected_by': shot['shot_boundaries'].get('detected_by') or 'manual',
                'confidence': shot['shot_boundaries'].get('confidence') or 'medium',
                'correlated_frames': shot['shot_boundaries'].get('correlated_frames') if isinstance(shot['shot_boundaries'].get('correlated_frames'), list) else [],
            }

        sanitized['chronological_shots'].append(sanitized_shot)

    return sanitized


def validate_frame_traceability(blueprint, timeline_frames_count):
    issues = []

    for shot in (blueprint.get('chronological_shots') or []):
        if not shot.get('frame_references') or len(shot['frame_references']) == 0:
            issues.append({
                'shot_index': shot.get('shot_index'),
                'issue': 'No frame references found',
                'severity': 'warning',
            })
            continue

        for ref in shot['frame_references']:
            if ref.get('frame_index', 0) >= timeline_frames_count:
                issues.append({
                    'shot_index': shot.get('shot_index'),
                    'issue': f'Frame index {ref["frame_index"]} exceeds timeline (max: {timeline_frames_count - 1})',
                    'severity': 'error',
                    'frame_index': ref['frame_index'],
                })

        time_range = shot.get('end_time_seconds', 0) - shot.get('start_time_seconds', 0)
        refs_in_range = [
            r for r in shot['frame_references']
            if shot.get('start_time_seconds', 0) <= r.get('timestamp_seconds', 0) <= shot.get('end_time_seconds', 0)
        ]

        if len(refs_in_range) == 0 and time_range > 3:
            issues.append({
                'shot_index': shot.get('shot_index'),
                'issue': f'No frame references within shot time range ({shot.get("start_time_seconds", 0)}s - {shot.get("end_time_seconds", 0)}s)',
                'severity': 'warning',
            })

    return issues
