import os
import re
import subprocess
import math
from pathlib import Path


def _normalize_path(target):
    if not isinstance(target, str):
        return target
    if '://' in target:
        return target
    is_windows_path = bool(re.match(r'^[a-zA-Z]:[\\/]', target))
    if is_windows_path:
        drive = target[0].lower()
        posix_path = target[2:].replace('\\', '/').lstrip('/')
        return f'/mnt/{drive}/{posix_path}'
    if re.match(r'^/mnt/[a-z]/', target, re.IGNORECASE):
        return target
    return os.path.abspath(target)


def _check_peepshow():
    try:
        result = subprocess.run(
            ['peepshow', '--help'],
            capture_output=True, text=True, timeout=10
        )
        return 'peepshow' in result.stdout or 'peepshow' in result.stderr
    except Exception:
        return False


def _compute_aspect_ratio(w, h):
    if not w or not h:
        return 'unknown'
    d = math.gcd(w, h)
    return f'{w // d}:{h // d}'


def _generate_simple_hash(input_str):
    h = 0
    for char in input_str:
        h = ((h << 5) - h) + ord(char)
        h = h & 0xFFFFFFFF
    return format(abs(h), '08x')


def _analyze_audio_mood(audio):
    if not audio:
        return None

    transcript = audio.get('transcript', {}).get('text', '') if isinstance(audio.get('transcript'), dict) else ''
    silence_ratio = audio.get('silenceRatio', 0)
    codec = audio.get('codec', '')

    mood_indicators = {
        'silence_dominant': silence_ratio > 0.5,
        'transcript_heavy': len(transcript) > 500,
        'music_detected': 'mp3' in codec.lower() or 'aac' in codec.lower(),
        'ambient': silence_ratio > 0.3 and len(transcript) < 100,
    }

    mood = 'neutral'

    if mood_indicators['silence_dominant']:
        mood = 'contemplative'
    if mood_indicators['ambient']:
        mood = 'atmospheric'
    if mood_indicators['music_detected'] and silence_ratio < 0.2:
        mood = 'dynamic'
    if mood_indicators['transcript_heavy']:
        mood = 'documentary'

    keywords = {
        'tense': ['tension', 'fear', 'danger', 'alarm', 'worried'],
        'emotional': ['love', 'happy', 'sad', 'cry', 'laugh', 'joy'],
        'action': ['run', 'explode', 'crash', 'fight', 'chase', 'fast'],
        'calm': ['quiet', 'peace', 'sleep', 'rest', 'slow', 'calm'],
    }

    lower_transcript = transcript.lower()
    for m, words in keywords.items():
        if any(w in lower_transcript for w in words):
            mood = m
            break

    return {
        'mood': mood,
        'indicators': mood_indicators,
        'confidence': 'medium' if silence_ratio > 0 or len(transcript) > 0 else 'low',
    }


def _detect_scene_changes(frames, options=None):
    if options is None:
        options = {}
    if not frames or len(frames) < 2:
        return []

    scene_changes = []
    motion_threshold = options.get('motion_threshold', 2.5)
    bytes_threshold = options.get('bytes_threshold', 0.4)
    consecutive_frames = options.get('consecutive_frames', False)

    for i in range(1, len(frames)):
        prev = frames[i - 1]
        curr = frames[i]

        motion_changed = prev.get('motion_level') != curr.get('motion_level')
        bytes_ratio = abs(curr.get('bytes', 0) - prev.get('bytes', 0)) / prev.get('bytes', 1) if prev.get('bytes', 0) > 0 else 0
        is_significant_motion_change = (
            (prev.get('motion_level') == 'high' and curr.get('motion_level') == 'low') or
            (prev.get('motion_level') == 'low' and curr.get('motion_level') == 'high')
        )
        is_bytes_spike = bytes_ratio > bytes_threshold

        if is_significant_motion_change or is_bytes_spike:
            scene_changes.append({
                'index': i,
                'timestamp_seconds': curr.get('timestamp_seconds', 0),
                'type': 'scene_cut' if is_bytes_spike else 'motion_change',
                'confidence': 'high' if (is_bytes_spike and is_significant_motion_change) else 'medium',
                'from_motion': prev.get('motion_level'),
                'to_motion': curr.get('motion_level'),
                'bytes_change_ratio': f'{bytes_ratio:.2f}',
            })
        elif consecutive_frames and motion_changed:
            scene_changes.append({
                'index': i,
                'timestamp_seconds': curr.get('timestamp_seconds', 0),
                'type': 'subtle_cut',
                'confidence': 'low',
                'from_motion': prev.get('motion_level'),
                'to_motion': curr.get('motion_level'),
                'bytes_change_ratio': f'{bytes_ratio:.2f}',
            })

    return scene_changes


def _extract_frame_metadata(frames, fps):
    if not frames or not isinstance(frames, list):
        return {'frames': [], 'scene_changes': []}

    frame_data = []
    for i, f in enumerate(frames):
        estimated_timestamp = i / fps if fps > 0 else 0

        motion_level = 'medium'
        if f.get('bytes'):
            if f['bytes'] < 30000:
                motion_level = 'low'
            elif f['bytes'] > 150000:
                motion_level = 'high'

        frame_data.append({
            'index': i,
            'path': f.get('path', ''),
            'bytes': f.get('bytes', 0),
            'timestamp_seconds': f.get('timestampSeconds', estimated_timestamp),
            'motion_level': f.get('motionLevel', motion_level),
            'frame_hash': f.get('hash', _generate_simple_hash(f.get('path', '') + str(i))),
        })

    scene_changes = _detect_scene_changes(frame_data)

    return {'frames': frame_data, 'scene_changes': scene_changes}


def ingest_video(video_target):
    print('🚀 VideoReverse: Step 1 — Ingestion & Sampling', flush=True)
    normalized = _normalize_path(video_target)
    print(f'🎥 Target: {video_target}', flush=True)
    if normalized != video_target:
        print(f'   → Resolved: {normalized}', flush=True)
    print(flush=True)

    peepshow_available = _check_peepshow()
    if not peepshow_available:
        print('❌ peepshow not found on PATH.', flush=True)
        print('   Fix: npm i -g peepshow', flush=True)
        print('   Requires Node.js 22+ (use nvm install 22)\n', flush=True)
        raise RuntimeError('peepshow not found')

    try:
        command = ['peepshow', normalized, '--emit', 'json', '--stats', 'off']

        result = subprocess.run(
            command,
            capture_output=True, text=True, check=True,
            timeout=300
        )

        stdout = result.stdout
        json_start = stdout.find('{')
        json_end = stdout.rfind('}')
        if json_start == -1 or json_end == -1:
            raise RuntimeError('peepshow output contained no JSON payload')

        raw = __import__('json').loads(stdout[json_start:json_end + 1])

        filename = normalized.split('/').pop() if '://' in normalized else os.path.basename(normalized)

        has_audio = bool(raw.get('audio', {}).get('path') and not raw.get('audio', {}).get('skippedReason'))
        audio_mood = _analyze_audio_mood(raw.get('audio', {}))
        timeline_frames = _extract_frame_metadata(raw.get('frames', []), raw.get('video', {}).get('fps', 30))

        video_info = raw.get('video', {})
        audio_info = raw.get('audio', {})
        extraction_info = raw.get('extraction', {})

        return {
            'pipeline_step': '1_ingestion_and_sampling',
            'video_metadata': {
                'filename': filename,
                'source_path': normalized,
                'duration_seconds': video_info.get('durationSeconds', 0),
                'width': video_info.get('width', 0),
                'height': video_info.get('height', 0),
                'dimensions': f'{video_info.get("width", 0)}x{video_info.get("height", 0)}',
                'aspect_ratio': _compute_aspect_ratio(video_info.get('width'), video_info.get('height')),
                'fps': video_info.get('fps', 0),
                'codec': video_info.get('codec', 'unknown'),
                'container': video_info.get('container', 'unknown'),
                'bitrate_kbps': video_info.get('bitrateKbps', 0),
            },
            'audio_data': {
                'has_audio': has_audio,
                'audio_path': audio_info.get('path'),
                'transcript': audio_info.get('transcript', {}).get('text', '') if isinstance(audio_info.get('transcript'), dict) else '',
                'transcript_segments': audio_info.get('transcript', {}).get('segments', []) if isinstance(audio_info.get('transcript'), dict) else [],
                'audio_codec': audio_info.get('codec'),
                'silence_ratio': audio_info.get('silenceRatio'),
                'mood': audio_mood,
            },
            'extraction': {
                'strategy': extraction_info.get('strategy', 'unknown'),
                'motion_signal_level': extraction_info.get('motionSignalLevel', 'unknown'),
                'frames_emitted': extraction_info.get('framesEmitted', 0),
                'frames_deduped': extraction_info.get('framesDeduped', 0),
                'elapsed_ms': extraction_info.get('elapsedMs', 0),
            },
            'timeline_frames': timeline_frames['frames'],
            'scene_changes': timeline_frames.get('scene_changes', []),
            'output_dir': raw.get('outputDir'),
        }
    except subprocess.CalledProcessError as error:
        print(f'❌ Step 1 failed: {error.stderr}', flush=True)
        raise RuntimeError(f'peepshow failed: {error.stderr}')
    except Exception as error:
        print(f'❌ Step 1 failed: {error}', flush=True)
        raise
