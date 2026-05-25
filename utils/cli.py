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
    "luma_dream_machine",
    "pika_2",
    "haiper_2",
    "stable_video_diffusion",
]

SUPPORTED_FORMATS = ["json", "txt", "both", "none"]
SUPPORTED_SAMPLE_MODES = ["full", "first-n", "highlights"]
SUPPORTED_LOG_LEVELS = ["debug", "info", "warn", "error", "quiet"]
SUPPORTED_GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
SUPPORTED_PROFILES = ["fast", "quality", "cheap"]

PROFILES: dict[str, dict[str, Any]] = {
    "fast": {
        "sample_mode": "first-n",
        "max_duration": 15,
        "gemini_model": "gemini-2.5-flash",
        "description": "Quick preview — first 15s, Flash model",
    },
    "quality": {
        "sample_mode": "full",
        "gemini_model": "gemini-2.5-pro",
        "description": "Best quality — full video, Pro model",
    },
    "cheap": {
        "sample_mode": "highlights",
        "max_duration": 10,
        "no_cache": True,
        "description": "Lowest cost — 10s highlights, no cache",
    },
}


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
        "max_retries": 5,
        "max_duration": None,
        "sample_mode": "full",
        "video_type": None,
        "no_cache": False,
        "no_transcribe": False,
        "wsl_mode": None,
        "gemini_model": "gemini-2.5-flash",
        "batch": None,
        "parallel": 4,
        "interactive": False,
        "profile": None,
        "compare_video": None,
    }

    # Pre-scan for --profile so profile defaults are set before explicit args override them
    for i, arg in enumerate(args):
        if arg == "--profile" and i + 1 < len(args):
            val = args[i + 1]
            if val in PROFILES:
                result["profile"] = val
                # Apply profile settings as base defaults
                for k, v in PROFILES[val].items():
                    if k != "description":
                        result[k] = v
            break

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

        elif arg in ("--interactive", "-i"):
            result["interactive"] = True

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

        elif arg == "--max-duration":
            i += 1
            if i < len(args):
                try:
                    duration = float(args[i])
                    if duration > 0:
                        result["max_duration"] = duration
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

        elif arg == "--batch":
            i += 1
            if i < len(args) and args[i]:
                result["batch"] = args[i]

        elif arg == "--parallel":
            i += 1
            if i < len(args):
                try:
                    parallel = int(args[i])
                    if parallel > 0:
                        result["parallel"] = parallel
                except ValueError:
                    pass

        elif arg == "--profile":
            i += 1
            # Already applied in pre-scan; just consume the value

        elif arg == "--compare":
            i += 1
            if i < len(args) and args[i]:
                result["compare_video"] = args[i]

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
  --explain-error      Print troubleshooting guide for an error code
                        Usage: --explain-error VR-101
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
  --max-duration       Pre-clip video to first N seconds
  --sample-mode        Sampling strategy: full (default), first-n (clip first Ns), highlights (30s best moments)
                        Requires ffmpeg. Reduces API cost by 50-90% for long videos (~$0.001/s for Gemini)
  --video-type         Override auto-detected video type
  --interactive, -i    Open REPL after pipeline completion for iterative prompt tuning
  --no-cache           Disable response caching
  --no-transcribe      Skip local Whisper transcription during ingest
  --wsl                Force WSL path conversion
  --win                Force Windows path mode
  --gemini-model       Gemini model for analysis: {", ".join(SUPPORTED_GEMINI_MODELS)} (default: gemini-2.5-flash)
  --batch <file>       Process all videos listed in a file (one path per line)
  --parallel <N>       Max concurrent videos in batch mode (default: 4)
  --profile <name>     Configuration preset: {", ".join(SUPPORTED_PROFILES)}
                         fast:   first 15s, Flash model (quick preview)
                         quality: full video, Pro model (best quality)
                         cheap:  10s highlights, no cache (lowest cost)
                         Explicit flags override profile settings.
  --compare <video>    Run pipeline on primary video and compare against this second video

Troubleshooting:
  --explain-error <VR-CODE>   Print detailed troubleshooting steps for an error

Examples:
  python -m src.main /mnt/e/vidrev/test1.mp4
  python -m src.main /mnt/e/vidrev/test1.mp4 --profile fast
  python -m src.main /mnt/e/vidrev/test1.mp4 --profile quality --model runway_gen4_5
  python -m src.main E:\\vidrev\\test1.mp4 --model runway_gen4_5,google_veo3_1
  python -m src.main /mnt/e/vidrev/test1.mp4 --format txt --verbose
  python -m src.main https://example.com/video.mp4 --dry-run
  python -m src.main --explain-error VR-101
  python -m src.main /mnt/e/vidrev/test1.mp4 --compare /mnt/e/vidrev/test_drone.mp4
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
