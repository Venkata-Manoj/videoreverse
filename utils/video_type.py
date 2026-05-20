VIDEO_TYPES = {
    'CGI': 'cgi',
    'LIVE_ACTION': 'live-action',
    'ANIMATION': 'animation',
    'SCREEN': 'screen',
    'DRONE': 'drone',
    'SOCIAL': 'social',
    'UNKNOWN': 'unknown',
}


def detect_video_type(metadata=None, extraction=None):
    dims = ''
    if metadata and metadata.get('width') and metadata.get('height'):
        dims = f'{metadata["width"]}x{metadata["height"]}'
    codec = metadata.get('codec', '') if metadata else ''
    motion_level = extraction.get('motion_signal_level', 'unknown') if extraction else 'unknown'

    codec_lower = codec.lower()
    if 'h264' in codec_lower or 'hevc' in codec_lower:
        if dims in ('1920x1080', '3840x2160'):
            if motion_level in ('medium', 'high'):
                return VIDEO_TYPES['LIVE_ACTION']
            return VIDEO_TYPES['DRONE']

    if 'png' in codec_lower or 'animation' in codec_lower:
        return VIDEO_TYPES['ANIMATION']

    if '720' in dims and motion_level == 'low':
        return VIDEO_TYPES['SCREEN']

    if '1080' in dims or '720' in dims:
        if motion_level == 'low':
            return VIDEO_TYPES['SCREEN']

    import re
    vertical_pattern = re.match(r'(\d+)x(\d+)', dims)
    if vertical_pattern:
        w, h = int(vertical_pattern.group(1)), int(vertical_pattern.group(2))
        if h > w:
            return VIDEO_TYPES['SOCIAL']

    if motion_level == 'high':
        return VIDEO_TYPES['CGI']

    return VIDEO_TYPES['UNKNOWN']


def get_video_type_label(video_type):
    labels = {
        VIDEO_TYPES['CGI']: 'CGI / 3D Animation',
        VIDEO_TYPES['LIVE_ACTION']: 'Live-Action Footage',
        VIDEO_TYPES['ANIMATION']: '2D Animation / Anime',
        VIDEO_TYPES['SCREEN']: 'Screen Recording / Tutorial',
        VIDEO_TYPES['DRONE']: 'Drone / Aerial Footage',
        VIDEO_TYPES['SOCIAL']: 'Social Media (Vertical)',
        VIDEO_TYPES['UNKNOWN']: 'Unknown Video Type',
    }
    return labels.get(video_type, 'Unknown')


def get_type_specific_schema(video_type):
    base_fields = {
        'art_style': 'cinematic',
        'color_grading': 'natural',
        'lighting_setup': 'natural',
    }

    type_schemas = {
        VIDEO_TYPES['CGI']: {
            **base_fields,
            'art_style': '3D CGI rendering',
            'color_grading': 'vibrant saturated colors',
            'lighting_setup': 'three-point studio lighting',
        },
        VIDEO_TYPES['ANIMATION']: {
            **base_fields,
            'art_style': '2D hand-drawn animation',
            'color_grading': 'anime cel-shaded colors',
            'lighting_setup': 'cel-shaded lighting',
        },
        VIDEO_TYPES['DRONE']: {
            **base_fields,
            'art_style': 'aerial cinematography',
            'color_grading': 'wide-angle natural colors',
            'lighting_setup': 'natural sunlight with shadows',
        },
        VIDEO_TYPES['SCREEN']: {
            **base_fields,
            'art_style': 'screen recording',
            'color_grading': 'neutral screen colors',
            'lighting_setup': 'screen glow lighting',
        },
        VIDEO_TYPES['SOCIAL']: {
            **base_fields,
            'art_style': 'social media vertical format',
            'color_grading': 'mobile-friendly bright colors',
            'lighting_setup': 'natural daylight',
        },
        VIDEO_TYPES['LIVE_ACTION']: {
            **base_fields,
            'art_style': 'live-action cinematography',
            'color_grading': 'cinematic color grading',
            'lighting_setup': 'location lighting',
        },
    }

    return type_schemas.get(video_type, base_fields)
