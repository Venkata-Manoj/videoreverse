from __future__ import annotations

import glob
import json
import math
import os
import subprocess
import tempfile
from collections.abc import Callable
from typing import Any, cast

from src.path_resolver import normalize_for_env

IngestProgressCallback = Callable[[str, str], None]


def _check_ffmpeg() -> bool:
    try:
        result = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def _compute_aspect_ratio(w: int | None, h: int | None) -> str:
    if not w or not h:
        return "unknown"
    d = math.gcd(w, h)
    return f"{w // d}:{h // d}"


def _generate_simple_hash(input_str: str) -> str:
    h = 0
    for char in input_str:
        h = ((h << 5) - h) + ord(char)
        h = h & 0xFFFFFFFF
    return format(abs(h), "08x")


def _emit_progress(callback: IngestProgressCallback | None, phase: str, message: str) -> None:
    if callback:
        callback(phase, message)


def _analyze_audio_mood(audio: dict[str, Any] | None) -> dict[str, Any] | None:
    if not audio:
        return None

    transcript = audio.get("transcript", {}).get("text", "") if isinstance(audio.get("transcript"), dict) else ""
    silence_ratio = audio.get("silenceRatio", 0)
    codec = audio.get("codec") or ""

    mood_indicators = {
        "silence_dominant": silence_ratio > 0.5,
        "transcript_heavy": len(transcript) > 500,
        "music_detected": "mp3" in codec.lower() or "aac" in codec.lower(),
        "ambient": silence_ratio > 0.3 and len(transcript) < 100,
    }

    mood = "neutral"

    if mood_indicators["silence_dominant"]:
        mood = "contemplative"
    if mood_indicators["ambient"]:
        mood = "atmospheric"
    if mood_indicators["music_detected"] and silence_ratio < 0.2:
        mood = "dynamic"
    if mood_indicators["transcript_heavy"]:
        mood = "documentary"

    keywords = {
        "tense": ["tension", "fear", "danger", "alarm", "worried"],
        "emotional": ["love", "happy", "sad", "cry", "laugh", "joy"],
        "action": ["run", "explode", "crash", "fight", "chase", "fast"],
        "calm": ["quiet", "peace", "sleep", "rest", "slow", "calm"],
    }

    lower_transcript = transcript.lower()
    for mood_name, words in keywords.items():
        if any(word in lower_transcript for word in words):
            mood = mood_name
            break

    return {
        "mood": mood,
        "indicators": mood_indicators,
        "confidence": "medium" if silence_ratio > 0 or len(transcript) > 0 else "low",
    }


def _detect_scene_changes(
    frames: list[dict[str, Any]],
    options: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if options is None:
        options = {}
    if not frames or len(frames) < 2:
        return []

    scene_changes = []
    bytes_threshold = options.get("bytes_threshold", 0.4)
    consecutive_frames = options.get("consecutive_frames", False)

    for i in range(1, len(frames)):
        prev = frames[i - 1]
        curr = frames[i]

        motion_changed = prev.get("motion_level") != curr.get("motion_level")
        bytes_ratio = abs(curr.get("bytes", 0) - prev.get("bytes", 0)) / prev.get("bytes", 1) if prev.get("bytes", 0) > 0 else 0
        is_significant_motion_change = (prev.get("motion_level") == "high" and curr.get("motion_level") == "low") or (
            prev.get("motion_level") == "low" and curr.get("motion_level") == "high"
        )
        is_bytes_spike = bytes_ratio > bytes_threshold

        if is_significant_motion_change or is_bytes_spike:
            scene_changes.append(
                {
                    "index": i,
                    "timestamp_seconds": curr.get("timestamp_seconds", 0),
                    "type": "scene_cut" if is_bytes_spike else "motion_change",
                    "confidence": "high" if (is_bytes_spike and is_significant_motion_change) else "medium",
                    "from_motion": prev.get("motion_level"),
                    "to_motion": curr.get("motion_level"),
                    "bytes_change_ratio": f"{bytes_ratio:.2f}",
                }
            )
        elif consecutive_frames and motion_changed:
            scene_changes.append(
                {
                    "index": i,
                    "timestamp_seconds": curr.get("timestamp_seconds", 0),
                    "type": "subtle_cut",
                    "confidence": "low",
                    "from_motion": prev.get("motion_level"),
                    "to_motion": curr.get("motion_level"),
                    "bytes_change_ratio": f"{bytes_ratio:.2f}",
                }
            )

    return scene_changes


def _extract_audio_for_transcription(video_path: str, temp_dir: str) -> str | None:
    audio_path = os.path.join(temp_dir, "audio_for_transcription.wav")
    extract_audio_cmd = [
        "ffmpeg",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        audio_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
    ]
    result = subprocess.run(extract_audio_cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0 or not os.path.exists(audio_path):
        return None
    return audio_path


def _transcribe_via_groq(audio_path: str) -> dict[str, Any] | None:
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                response_format="verbose_json",
            )
    except Exception:
        return None

    return {
        "text": (getattr(result, "text", "") or "").strip(),
        "segments": [
            {"start": s.start, "end": s.end, "text": (s.text or "").strip()}
            for s in getattr(result, "segments", []) or []
        ],
        "status": "complete",
        "reason": None,
    }


def _transcribe_local(audio_path: str, model_name: str) -> dict[str, Any]:
    try:
        import whisper  # type: ignore[import-not-found]
    except ImportError:
        return {
            "text": "",
            "segments": [],
            "status": "skipped",
            "reason": "openai-whisper is not installed",
        }

    model = whisper.load_model(model_name)
    raw_result = cast(dict[str, Any], model.transcribe(audio_path, fp16=False, verbose=False))
    segments = [
        {
            "start": segment.get("start"),
            "end": segment.get("end"),
            "text": (segment.get("text") or "").strip(),
        }
        for segment in raw_result.get("segments", []) or []
    ]
    return {
        "text": (raw_result.get("text") or "").strip(),
        "segments": segments,
        "status": "complete",
        "reason": None,
    }


def _transcribe_audio(audio_path: str, model_name: str) -> dict[str, Any]:
    groq_result = _transcribe_via_groq(audio_path)
    if groq_result is not None:
        return groq_result
    return _transcribe_local(audio_path, model_name)


def ingest_video(
    video_target: str,
    *,
    options: dict[str, Any] | None = None,
    on_progress: IngestProgressCallback | None = None,
) -> dict[str, Any]:
    if options is None:
        options = {}

    print("VideoReverse: Step 1 - Ingestion & Sampling", flush=True)
    normalized = normalize_for_env(video_target)
    print(f"Target: {video_target}", flush=True)
    if normalized != video_target:
        print(f"  -> Resolved: {normalized}", flush=True)
    print(flush=True)

    ffmpeg_available = _check_ffmpeg()
    if not ffmpeg_available:
        print("Step 1 failed: ffmpeg not found on PATH.", flush=True)
        print("  Fix: apt install ffmpeg  (or brew install ffmpeg)", flush=True)
        raise RuntimeError("ffmpeg not found")

    try:
        filename = normalized.split("/").pop() if "://" in normalized else os.path.basename(normalized)

        _emit_progress(on_progress, "probe", "Inspecting video streams with ffprobe")
        probe_cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            normalized,
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True, timeout=60)
        probe_data = json.loads(probe_result.stdout)

        video_stream = next((stream for stream in probe_data.get("streams", []) if stream.get("codec_type") == "video"), {})
        audio_stream = next((stream for stream in probe_data.get("streams", []) if stream.get("codec_type") == "audio"), {})
        fmt = probe_data.get("format", {})

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        fps_str = video_stream.get("r_frame_rate", "30/1")
        fps_num, fps_den = map(int, fps_str.split("/")) if "/" in fps_str else (30, 1)
        fps = fps_num / fps_den if fps_den else 30
        duration = float(fmt.get("duration", 0))
        codec = video_stream.get("codec_name", "unknown")
        container = os.path.splitext(normalized)[1].lstrip(".") or "unknown"
        bitrate = int(fmt.get("bit_rate", 0)) // 1000 if fmt.get("bit_rate") else 0

        has_audio = bool(audio_stream)
        audio_codec = audio_stream.get("codec_name")

        temp_dir = tempfile.mkdtemp(prefix="vidrev-frames-")
        _emit_progress(on_progress, "frames", "Extracting keyframes with ffmpeg")
        frame_pattern = os.path.join(temp_dir, "frame_%04d.jpg")
        extract_cmd = [
            "ffmpeg",
            "-i",
            normalized,
            "-vf",
            "select='eq(pict_type,I)',showinfo",
            "-vsync",
            "vfr",
            "-q:v",
            "2",
            frame_pattern,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
        ]
        subprocess.run(extract_cmd, capture_output=True, text=True, timeout=300)

        frame_files = sorted(glob.glob(frame_pattern.replace("%04d.jpg", "*.jpg")))
        timeline_frames = []
        for i, frame_path in enumerate(frame_files):
            timestamp = i / fps if fps > 0 else 0
            frame_size = os.path.getsize(frame_path)
            motion_level = "low" if frame_size < 30000 else ("high" if frame_size > 150000 else "medium")
            timeline_frames.append(
                {
                    "index": i,
                    "path": frame_path,
                    "bytes": frame_size,
                    "timestamp_seconds": timestamp,
                    "motion_level": motion_level,
                    "frame_hash": _generate_simple_hash(frame_path + str(i)),
                }
            )

        scene_changes = _detect_scene_changes(timeline_frames)

        transcript = ""
        transcript_segments: list[dict[str, Any]] = []
        transcript_status = "disabled" if options.get("no_transcribe") else "not_requested"
        transcript_reason = "transcription disabled by user" if options.get("no_transcribe") else None
        audio_path = None

        if has_audio and not options.get("no_transcribe"):
            _emit_progress(on_progress, "transcribe", "Preparing local audio transcription")
            audio_path = _extract_audio_for_transcription(normalized, temp_dir)
            if audio_path:
                _emit_progress(on_progress, "transcribe", "Running Whisper transcription")
                transcription = _transcribe_audio(audio_path, options.get("whisper_model", "tiny"))
                transcript = transcription["text"]
                transcript_segments = transcription["segments"]
                transcript_status = transcription["status"]
                transcript_reason = transcription["reason"]
            else:
                transcript_status = "skipped"
                transcript_reason = "ffmpeg could not extract audio for transcription"
        elif not has_audio:
            transcript_status = "skipped"
            transcript_reason = "video has no audio stream"

        audio_data = {
            "has_audio": has_audio,
            "audio_path": audio_path,
            "transcript": transcript,
            "transcript_segments": transcript_segments,
            "audio_codec": audio_codec,
            "silence_ratio": None,
            "transcription_status": transcript_status,
            "transcription_reason": transcript_reason,
            "mood": _analyze_audio_mood({"codec": audio_codec, "silenceRatio": 0, "transcript": {"text": transcript}}),
        }

        return {
            "pipeline_step": "1_ingestion_and_sampling",
            "video_metadata": {
                "filename": filename,
                "source_path": normalized,
                "duration_seconds": duration,
                "width": width,
                "height": height,
                "dimensions": f"{width}x{height}",
                "aspect_ratio": _compute_aspect_ratio(width, height),
                "fps": fps,
                "codec": codec,
                "container": container,
                "bitrate_kbps": bitrate,
            },
            "audio_data": audio_data,
            "extraction": {
                "strategy": "ffmpeg_keyframes",
                "motion_signal_level": "medium",
                "frames_emitted": len(timeline_frames),
                "frames_deduped": len(timeline_frames),
                "elapsed_ms": 0,
            },
            "timeline_frames": timeline_frames,
            "scene_changes": scene_changes,
            "output_dir": temp_dir,
        }
    except subprocess.CalledProcessError as error:
        print(f"Step 1 failed: {error.stderr}", flush=True)
        raise RuntimeError(f"ffmpeg failed: {error.stderr}") from error
    except Exception as error:
        print(f"Step 1 failed: {error}", flush=True)
        raise
