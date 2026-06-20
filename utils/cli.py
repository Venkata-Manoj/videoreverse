from __future__ import annotations

import os
import platform
from typing import Any

DEFAULT_OUTPUT_DIR = "output_blueprints"
DEFAULT_FORMAT = "both"
DEFAULT_LOG_LEVEL = "info"

SUPPORTED_MODELS = [
    "runway_gen4_5",
    "google_veo3_1",
    "kling_3_0",
    "sora_2",
    "luma_ray2",
    "luma_dream_machine",
    "pika_3_0",
    "pika_2",
    "haiper_2",
    "stable_video_diffusion",
]

SUPPORTED_FORMATS = ["json", "txt", "both", "none"]
SUPPORTED_SAMPLE_MODES = ["full", "first-n", "highlights"]
SUPPORTED_LOG_LEVELS = ["debug", "info", "warn", "error", "quiet"]
SUPPORTED_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
]


def parse_cli_args(args: list[str] | None = None) -> dict[str, Any]:
    import sys

    if args is None:
        args = sys.argv[1:]

    result = {
        "video_path": None,
        "models": None,
        "output_dir": DEFAULT_OUTPUT_DIR,
        "format": DEFAULT_FORMAT,
        "log_level": DEFAULT_LOG_LEVEL,
        "dry_run": False,
        "verbose": False,
        "quiet": False,
        "force": False,
        "max_retries": 3,
        "max_duration": None,
        "sample_mode": "full",
        "video_type": None,
        "no_cache": False,
        "no_transcribe": False,
        "wsl_mode": None,
        "gemini_model": "gemini-2.5-flash",
        "frames_only": False,
        "mock": False,
        "blur_threshold": 100,
        "aggressive_blur_filter": False,
    }

    i = 0
    while i < len(args):
        arg = args[i]

        if arg in ("--help", "-h"):
            result["show_help"] = True

        elif arg in ("--model", "-m"):
            i += 1
            if i < len(args) and args[i]:
                result["models"] = [m.strip() for m in args[i].split(",") if m.strip()]

        elif arg in ("--output-dir", "-o"):
            i += 1
            if i < len(args) and args[i]:
                result["output_dir"] = args[i]

        elif arg in ("--format", "-f"):
            i += 1
            if i < len(args) and args[i] in SUPPORTED_FORMATS:
                result["format"] = args[i]
            elif i < len(args):
                raise ValueError(f'Invalid format "{args[i]}". Use: {", ".join(SUPPORTED_FORMATS)}')

        elif arg in ("--log-level", "-l"):
            i += 1
            if i < len(args) and args[i] in SUPPORTED_LOG_LEVELS:
                result["log_level"] = args[i]
            elif i < len(args):
                raise ValueError(f'Invalid log level "{args[i]}". Use: {", ".join(SUPPORTED_LOG_LEVELS)}')

        elif arg in ("--verbose", "-v"):
            result["verbose"] = True
            result["log_level"] = "debug"

        elif arg in ("--quiet", "-q"):
            result["quiet"] = True
            result["log_level"] = "quiet"

        elif arg == "--dry-run":
            result["dry_run"] = True

        elif arg in ("--force", "-F"):
            result["force"] = True

        elif arg in ("--max-retries", "-r"):
            i += 1
            if i < len(args):
                try:
                    retries = int(args[i])
                    if retries >= 0:
                        result["max_retries"] = retries
                except ValueError:
                    pass

        elif arg == "--max-frames":
            i += 1
            if i < len(args):
                try:
                    n = int(args[i])
                    if n >= 2:
                        result["max_frames"] = n
                except ValueError:
                    pass

        elif arg == "--max-duration":
            i += 1
            if i < len(args):
                try:
                    duration = float(args[i])
                    if duration > 0:
                        result["max_duration"] = duration
                except ValueError:
                    pass

        elif arg == "--rate-limit-rpm":
            i += 1
            if i < len(args):
                try:
                    rpm = float(args[i])
                    if rpm > 0:
                        result["rate_limit_rpm"] = rpm
                except ValueError:
                    pass

        elif arg == "--sample-mode":
            i += 1
            if i < len(args) and args[i] in SUPPORTED_SAMPLE_MODES:
                result["sample_mode"] = args[i]
            elif i < len(args):
                raise ValueError(f'Invalid sample mode "{args[i]}". Use: {", ".join(SUPPORTED_SAMPLE_MODES)}')

        elif arg == "--video-type":
            i += 1
            if i < len(args) and args[i]:
                result["video_type"] = args[i]

        elif arg == "--no-compress":
            result["no_compress"] = True

        elif arg == "--compress-width":
            i += 1
            if i < len(args):
                try:
                    w = int(args[i])
                    if w >= 360:
                        result["compress_width"] = w
                except ValueError:
                    pass

        elif arg == "--no-cache":
            result["no_cache"] = True

        elif arg == "--no-transcribe":
            result["no_transcribe"] = True

        elif arg == "--wsl":
            result["wsl_mode"] = "wsl"

        elif arg == "--win":
            result["wsl_mode"] = "win"

        elif arg == "--gemini-model":
            i += 1
            if i < len(args) and args[i] in SUPPORTED_GEMINI_MODELS:
                result["gemini_model"] = args[i]
            elif i < len(args):
                raise ValueError(f'Invalid Gemini model "{args[i]}". Use: {", ".join(SUPPORTED_GEMINI_MODELS)}')

        elif arg in ("--frames-only", "--no-file-api"):
            result["frames_only"] = True

        elif arg == "--mock":
            result["mock"] = True

        elif arg == "--blur-threshold":
            i += 1
            if i < len(args):
                try:
                    t = float(args[i])
                    if t >= 0:
                        result["blur_threshold"] = t
                except ValueError:
                    pass

        elif arg == "--aggressive-blur-filter":
            result["aggressive_blur_filter"] = True

        else:
            if not arg.startswith("-") and result["video_path"] is None:
                result["video_path"] = arg

        i += 1

    if result["models"]:
        invalid = [m for m in result["models"] if m not in SUPPORTED_MODELS]
        if invalid:
            raise ValueError(f"Unsupported models: {', '.join(invalid)}. Supported: {', '.join(SUPPORTED_MODELS)}")

    return result


def print_help() -> None:
    help_text = f"""
VideoReverse — Universal Video-to-Prompt Pipeline

Usage:
  python -m src.main <video_path_or_url> [options]

Arguments:
  video_path_or_url    Path to video file or URL

Options:
  --help, -h           Show this help message
  --model, -m          Generate prompts only for specific models (comma-separated)
                        Options: {", ".join(SUPPORTED_MODELS)}
  --output-dir, -o      Custom output directory (default: {DEFAULT_OUTPUT_DIR})
  --format             Output format: {", ".join(SUPPORTED_FORMATS)} (default: both)
  --log-level, -l      Log level: {", ".join(SUPPORTED_LOG_LEVELS)} (default: info)
  --verbose, -v        Enable verbose logging (alias for --log-level debug)
  --quiet, -q          Suppress console output (alias for --log-level quiet)
  --dry-run            Output prompts without saving files
  --force, -F          Skip failed steps and use cached results
  --max-retries, -r    Max retry attempts for API calls (default: 3)
  --max-frames         Max frames to extract (default: 60, reduces token usage)
  --max-duration       Pre-clip video to first N seconds
  --sample-mode        Sampling strategy: full (default), first-n (clip first Ns), highlights (30s best moments)
                        Requires ffmpeg. Reduces API cost by 50-90% for long videos (~$0.001/s for Gemini)
  --video-type         Override auto-detected video type
  --no-compress        Skip video compression before API upload
  --compress-width     Target width for compression (default: 720, min: 360)
  --no-cache           Disable response caching
  --no-transcribe      Skip local Whisper transcription during ingest
  --wsl                Force WSL path conversion
  --win                Force Windows path mode
  --rate-limit-rpm     Max API requests per minute (default: 5, for free tier; set higher for paid)
  --gemini-model       Gemini model for analysis: {", ".join(SUPPORTED_GEMINI_MODELS)} (default: gemini-2.5-flash)
  --frames-only        Send extracted frames as inline images instead of uploading the full
                        video via Gemini File API. Token cost bounded by --max-frames regardless
                        of video duration. Reduces latency and 429/503 risk for long videos.
  --no-file-api         Alias for --frames-only
  --blur-threshold FLOAT  Minimum sharpness score (Laplacian variance normalized).
                            Higher = stricter. Default 100 works for 720p-4K.
                            Set 0 to disable. High-motion frames always preserved.
  --aggressive-blur-filter
                            Also drop blurry high-motion frames when both neighbors are
                            sharp (transient pan/zoom artifacts). Only meaningful with
                            --blur-threshold (default 100).
  --mock               Skip API calls, generate a synthetic blueprint from metadata (zero cost)

Examples:
  python -m src.main test1.mp4
  python -m src.main test1.mp4 --model runway_gen4_5,google_veo3_1
  python -m src.main test1.mp4 --format txt --verbose
  python -m src.main https://example.com/video.mp4 --dry-run
"""
    print(help_text)


def detect_environment() -> str:
    is_wsl = False
    if os.path.exists("/proc/version"):
        try:
            with open("/proc/version") as f:
                content = f.read().lower()
                is_wsl = "microsoft" in content
        except Exception:
            pass

    if is_wsl:
        return "wsl"
    if platform.system() == "Windows":
        return "win"
    return "unix"
