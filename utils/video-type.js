export const VIDEO_TYPES = {
    CGI: 'cgi',
    LIVE_ACTION: 'live-action',
    ANIMATION: 'animation',
    SCREEN: 'screen',
    DRONE: 'drone',
    SOCIAL: 'social',
    UNKNOWN: 'unknown',
};

export function detectVideoType(metadata, extraction) {
    const dims = metadata?.width && metadata?.height ? `${metadata.width}x${metadata.height}` : '';
    const codec = metadata?.codec || '';
    const motionLevel = extraction?.motion_signal_level || 'unknown';

    if (codec.toLowerCase().includes('h264') || codec.toLowerCase().includes('hevc')) {
        if (dims === '1920x1080' || dims === '3840x2160') {
            if (motionLevel === 'medium' || motionLevel === 'high') {
                return VIDEO_TYPES.LIVE_ACTION;
            }
            return VIDEO_TYPES.DRONE;
        }
    }

    if (codec.toLowerCase().includes('png') || codec.toLowerCase().includes('animation')) {
        return VIDEO_TYPES.ANIMATION;
    }

    if (dims.includes('720') && motionLevel === 'low') {
        return VIDEO_TYPES.SCREEN;
    }

    if (dims.includes('1080') || dims.includes('720')) {
        if (motionLevel === 'low') {
            return VIDEO_TYPES.SCREEN;
        }
    }

    const verticalPattern = dims.match(/(\d+)x(\d+)/);
    if (verticalPattern) {
        const [, w, h] = verticalPattern;
        if (parseInt(h) > parseInt(w)) {
            return VIDEO_TYPES.SOCIAL;
        }
    }

    if (motionLevel === 'high') {
        return VIDEO_TYPES.CGI;
    }

    return VIDEO_TYPES.UNKNOWN;
}

export function getVideoTypeLabel(videoType) {
    const labels = {
        [VIDEO_TYPES.CGI]: 'CGI / 3D Animation',
        [VIDEO_TYPES.LIVE_ACTION]: 'Live-Action Footage',
        [VIDEO_TYPES.ANIMATION]: '2D Animation / Anime',
        [VIDEO_TYPES.SCREEN]: 'Screen Recording / Tutorial',
        [VIDEO_TYPES.DRONE]: 'Drone / Aerial Footage',
        [VIDEO_TYPES.SOCIAL]: 'Social Media (Vertical)',
        [VIDEO_TYPES.UNKNOWN]: 'Unknown Video Type',
    };
    return labels[videoType] || 'Unknown';
}

export function getTypeSpecificSchema(videoType) {
    const baseFields = {
        art_style: 'cinematic',
        color_grading: 'natural',
        lighting_setup: 'natural',
    };

    switch (videoType) {
        case VIDEO_TYPES.CGI:
            return {
                ...baseFields,
                art_style: '3D CGI rendering',
                color_grading: 'vibrant saturated colors',
                lighting_setup: 'three-point studio lighting',
            };

        case VIDEO_TYPES.ANIMATION:
            return {
                ...baseFields,
                art_style: '2D hand-drawn animation',
                color_grading: 'anime cel-shaded colors',
                lighting_setup: 'cel-shaded lighting',
            };

        case VIDEO_TYPES.DRONE:
            return {
                ...baseFields,
                art_style: 'aerial cinematography',
                color_grading: 'wide-angle natural colors',
                lighting_setup: 'natural sunlight with shadows',
            };

        case VIDEO_TYPES.SCREEN:
            return {
                ...baseFields,
                art_style: 'screen recording',
                color_grading: 'neutral screen colors',
                lighting_setup: 'screen glow lighting',
            };

        case VIDEO_TYPES.SOCIAL:
            return {
                ...baseFields,
                art_style: 'social media vertical format',
                color_grading: 'mobile-friendly bright colors',
                lighting_setup: 'natural daylight',
            };

        case VIDEO_TYPES.LIVE_ACTION:
            return {
                ...baseFields,
                art_style: 'live-action cinematography',
                color_grading: 'cinematic color grading',
                lighting_setup: 'location lighting',
            };

        default:
            return baseFields;
    }
}