from __future__ import annotations

from enum import Enum
from typing import Any


class VRErrorCode(Enum):
    """VideoReverse error codes — VR-XXX format for CLI, pipeline, and web."""

    # Input & Configuration (001–099)
    MISSING_VIDEO_PATH = ("VR-001", "No video path provided")
    INVALID_MODEL = ("VR-002", "Unsupported model specified")
    INVALID_ARGUMENT = ("VR-003", "Invalid CLI argument or option")
    FILE_NOT_FOUND = ("VR-004", "Video file not found or inaccessible")
    PATH_RESOLUTION_FAILED = ("VR-005", "Failed to resolve video path")
    URL_DOWNLOAD_FAILED = ("VR-006", "Failed to download video from URL")
    INVALID_FORMAT = ("VR-007", "Invalid output format specified")
    CONFIG_PROFILE_NOT_FOUND = ("VR-008", "Configuration profile not found")

    # FFmpeg / Ingestion (101–199)
    FFMPEG_NOT_FOUND = ("VR-101", "FFmpeg not found on system PATH")
    FFPROBE_FAILED = ("VR-102", "FFprobe failed to read video metadata")
    FRAME_EXTRACTION_FAILED = ("VR-103", "FFmpeg keyframe extraction failed")
    AUDIO_EXTRACTION_FAILED = ("VR-104", "FFmpeg audio extraction failed")
    TRANSCRIPTION_FAILED = ("VR-105", "Whisper transcription failed")
    SAMPLING_FAILED = ("VR-106", "Smart frame sampling failed")
    VIDEO_CORRUPT = ("VR-107", "Video file appears corrupt or unreadable")
    UNSUPPORTED_CODEC = ("VR-108", "Video codec not supported by ffmpeg")

    # Gemini API (201–299)
    GEMINI_KEY_MISSING = ("VR-201", "GEMINI_API_KEY environment variable not set")
    GEMINI_FILE_UPLOAD_FAILED = ("VR-202", "Gemini File API upload failed")
    GEMINI_SYNTHESIS_FAILED = ("VR-203", "Gemini blueprint synthesis failed")
    GEMINI_RATE_LIMITED = ("VR-204", "Gemini API rate limit exceeded")
    GEMINI_SERVICE_DOWN = ("VR-205", "Gemini service temporarily unavailable")
    GEMINI_QUOTA_EXCEEDED = ("VR-206", "Gemini API quota exhausted")
    GEMINI_INVALID_RESPONSE = ("VR-207", "Gemini returned invalid or malformed response")

    # Processing / Compilation (301–399)
    COMPILATION_FAILED = ("VR-301", "Prompt compilation failed")
    BLUEPRINT_VALIDATION_FAILED = ("VR-302", "Blueprint validation failed")
    FALLBACK_ACTIVATED = ("VR-303", "Fallback mode activated — reduced quality")
    CACHE_READ_FAILED = ("VR-304", "Failed to read cached blueprint")
    CACHE_WRITE_FAILED = ("VR-305", "Failed to write blueprint to cache")
    BATCH_ITEM_FAILED = ("VR-306", "Batch item processing failed")

    # System / Output (401–499)
    OUTPUT_DIR_CREATE_FAILED = ("VR-401", "Failed to create output directory")
    OUTPUT_WRITE_FAILED = ("VR-402", "Failed to write output file")
    TEMP_FILE_CLEANUP_FAILED = ("VR-403", "Temporary file cleanup failed")
    PIPELINE_HISTORY_WRITE_FAILED = ("VR-404", "Failed to write pipeline history")
    INTERNAL_ERROR = ("VR-499", "Unexpected internal error")

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        category = self.code.split("-")[0]
        return {"code": self.code, "message": self.message, "category": category}


class VRError(Exception):
    """Exception carrying a VRErrorCode for standardized error handling."""

    def __init__(
        self,
        code: VRErrorCode,
        detail: str | None = None,
        cause: Exception | None = None,
    ):
        self.code_obj = code
        self.code = code.code
        self.message = code.message
        self.detail = detail
        self.cause = cause
        messages = [f"{code.code}: {code.message}"]
        if detail:
            messages.append(detail)
        super().__init__(" — ".join(messages))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "cause": str(self.cause) if self.cause else None,
        }


TROUBLESHOOTING: dict[str, dict[str, Any]] = {
    "VR-001": {
        "title": "No Video Path Provided",
        "summary": "You must specify a video file path or URL.",
        "steps": [
            "Run: python -m src.main <path_to_video>",
            "Example: python -m src.main ./test1.mp4",
            "Example: python -m src.main E:\\videos\\clip.mp4",
            "Example: python -m src.main https://example.com/video.mp4",
        ],
    },
    "VR-002": {
        "title": "Unsupported Model",
        "summary": "The specified model ID is not in the supported list.",
        "steps": [
            "Run: python -m src.main --help to list supported models",
            "Supported: runway_gen4_5, google_veo3_1, kling_3_0, sora_2, luma_dream_machine, pika_2, haiper_2, stable_video_diffusion",
            "Check spelling of the model ID",
        ],
    },
    "VR-003": {
        "title": "Invalid CLI Argument",
        "summary": "A CLI flag or value was unrecognized or invalid.",
        "steps": [
            "Run: python -m src.main --help to see all options",
            "Check that values match expected options",
            "Ensure flags are separated by spaces",
        ],
    },
    "VR-004": {
        "title": "File Not Found",
        "summary": "The video file does not exist at the given path.",
        "steps": [
            "Verify the file path is correct",
            "Check that the file has not been moved or deleted",
            "If using a Windows path in WSL, ensure it auto-converts (e.g., E:\\vidrev\\test.mp4 → /mnt/e/vidrev/test.mp4)",
            "Use --wsl or --win to force path mode",
        ],
    },
    "VR-005": {
        "title": "Path Resolution Failed",
        "summary": "Could not normalize or resolve the video path.",
        "steps": [
            "Ensure the path does not contain special characters",
            "Try using an absolute path instead of relative",
            "If on Windows, use forward slashes or double backslashes",
        ],
    },
    "VR-101": {
        "title": "FFmpeg Not Found",
        "summary": "FFmpeg is required but not installed or not on PATH.",
        "steps": [
            "Install ffmpeg: sudo apt-get install ffmpeg (Ubuntu/Debian)",
            "Install ffmpeg: brew install ffmpeg (macOS)",
            "Install ffmpeg: Download from https://ffmpeg.org/download.html (Windows)",
            "Verify with: ffmpeg -version",
        ],
    },
    "VR-102": {
        "title": "FFprobe Failed",
        "summary": "FFprobe could not read metadata from the video file.",
        "steps": [
            "Verify the file is a valid video format (MP4, MOV, AVI, WebM)",
            "Try: ffprobe <video_path> to see the raw error",
            "The file may be corrupt — try re-encoding with HandBrake",
        ],
    },
    "VR-103": {
        "title": "Frame Extraction Failed",
        "summary": "FFmpeg could not extract keyframes from the video.",
        "steps": [
            "Check video file integrity",
            "Try shortening the video or using --sample-mode first-n",
            "Ensure sufficient disk space for temporary frames",
        ],
    },
    "VR-201": {
        "title": "Gemini API Key Missing",
        "summary": "The GEMINI_API_KEY environment variable is not set.",
        "steps": [
            "Get a free API key from https://aistudio.google.com/",
            "Create .env file: cp .env.example .env",
            "Add your key: GEMINI_API_KEY=your_key_here",
            "Restart the application",
        ],
    },
    "VR-202": {
        "title": "Gemini File Upload Failed",
        "summary": "Could not upload the video to Gemini File API.",
        "steps": [
            "Check your internet connection",
            "Verify GEMINI_API_KEY is valid and not expired",
            "The video file may be too large — try --sample-mode highlights",
            "Check Gemini API status at https://status.cloud.google.com/",
        ],
    },
    "VR-203": {
        "title": "Gemini Synthesis Failed",
        "summary": "Gemini returned an error during blueprint analysis.",
        "steps": [
            "This is usually a transient error — retry with --max-retries 5",
            "If persistent, try a different --gemini-model (e.g., gemini-2.0-flash)",
            "The video content may be too complex — use --sample-mode first-n",
            "Enable fallback: fallback is on by default",
        ],
    },
    "VR-204": {
        "title": "Gemini Rate Limited",
        "summary": "Too many API requests in a short period.",
        "steps": [
            "Wait 1-2 minutes before retrying",
            "Reduce parallel processing: --parallel 2",
            "Enable caching: remove --no-cache flag",
            "Use highlights mode to reduce video size: --sample-mode highlights --max-duration 10",
        ],
    },
    "VR-301": {
        "title": "Prompt Compilation Failed",
        "summary": "Could not compile prompts from the blueprint and templates.",
        "steps": [
            "Verify prompt_templates.json is valid JSON",
            "Check template placeholders match the blueprint schema",
            "If fallback is active, fallback prompts were used instead",
        ],
    },
    "VR-302": {
        "title": "Blueprint Validation Failed",
        "summary": "The generated blueprint did not pass schema validation.",
        "steps": [
            "Auto-sanitization was attempted — results may be degraded",
            "Try a different --gemini-model for better results",
            "This may indicate a Gemini API change — report the issue",
        ],
    },
    "VR-402": {
        "title": "Output Write Failed",
        "summary": "Could not write output files to disk.",
        "steps": [
            "Check that the output directory exists and is writable",
            "Use --output-dir to specify a different path",
            "Ensure sufficient disk space",
        ],
    },
    "VR-499": {
        "title": "Internal Error",
        "summary": "An unexpected error occurred that does not have a specific error code.",
        "steps": [
            "Check the full error message and stack trace above",
            "Report the issue at https://github.com/Venkata-Manoj/videoreverse/issues",
            "Include the full command, error output, and video type",
            "Try running with --verbose for more details",
        ],
    },
}


def get_troubleshooting(code: str) -> dict[str, Any]:
    return TROUBLESHOOTING.get(code, {
        "title": "Unknown Error",
        "summary": "No troubleshooting information available for this error.",
        "steps": ["Try running with --verbose for more details", "Report the issue at https://github.com/Venkata-Manoj/videoreverse/issues"],
    })


def explain_error(code: str) -> str:
    info = get_troubleshooting(code)
    lines = [
        f"═══════════════════════════════════════════",
        f"  {code} — {info['title']}",
        f"═══════════════════════════════════════════",
        f"",
        f"  {info['summary']}",
        f"",
        f"  How to fix:",
    ]
    for i, step in enumerate(info["steps"], 1):
        lines.append(f"    {i}. {step}")
    lines += [
        f"",
        f"  For more help: https://github.com/Venkata-Manoj/videoreverse/issues",
        f"═══════════════════════════════════════════",
    ]
    return "\n".join(lines)


def format_error(code: VRErrorCode, detail: str | None = None) -> str:
    msg = f"[{code.code}] {code.message}"
    if detail:
        msg += f" — {detail}"
    return msg


def resolve_error_code(err: Exception) -> VRErrorCode | None:
    if isinstance(err, VRError):
        return err.code_obj
    err_str = str(err).lower()

    checks: list[tuple[str, VRErrorCode]] = [
        ("ffmpeg not found", VRErrorCode.FFMPEG_NOT_FOUND),
        ("ffprobe", VRErrorCode.FFPROBE_FAILED),
        ("gemini_api_key", VRErrorCode.GEMINI_KEY_MISSING),
        ("api key", VRErrorCode.GEMINI_KEY_MISSING),
        ("rate limit", VRErrorCode.GEMINI_RATE_LIMITED),
        ("429", VRErrorCode.GEMINI_RATE_LIMITED),
        ("503", VRErrorCode.GEMINI_SERVICE_DOWN),
        ("quota", VRErrorCode.GEMINI_QUOTA_EXCEEDED),
        ("file not found", VRErrorCode.FILE_NOT_FOUND),
        ("no such file", VRErrorCode.FILE_NOT_FOUND),
        ("compile", VRErrorCode.COMPILATION_FAILED),
        ("extract", VRErrorCode.FRAME_EXTRACTION_FAILED),
        ("transcrib", VRErrorCode.TRANSCRIPTION_FAILED),
        ("output dir", VRErrorCode.OUTPUT_DIR_CREATE_FAILED),
        ("write", VRErrorCode.OUTPUT_WRITE_FAILED),
        ("unsupported format", VRErrorCode.INVALID_FORMAT),
        ("invalid model", VRErrorCode.INVALID_MODEL),
        ("unable to locate", VRErrorCode.FFMPEG_NOT_FOUND),
        ("not found on path", VRErrorCode.FFMPEG_NOT_FOUND),
        ("sampl", VRErrorCode.SAMPLING_FAILED),
        ("corrupt", VRErrorCode.VIDEO_CORRUPT),
        ("validation", VRErrorCode.BLUEPRINT_VALIDATION_FAILED),
        ("cache", VRErrorCode.CACHE_READ_FAILED),
        ("cleanup", VRErrorCode.TEMP_FILE_CLEANUP_FAILED),
    ]
    for pattern, code in checks:
        if pattern in err_str:
            return code
    return None


def print_error_report(code: VRErrorCode, detail: str | None = None) -> None:
    msg = f"[{code.code}] {code.message}"
    if detail:
        msg += f"\n  → {detail}"
    print(f"\n  ❌ {msg}", flush=True)

    info = get_troubleshooting(code.code)
    print(f"\n  Troubleshooting for {code.code}:", flush=True)
    for i, step in enumerate(info["steps"], 1):
        print(f"    {i}. {step}", flush=True)
    print(f"\n  For more help: https://github.com/Venkata-Manoj/videoreverse/issues\n", flush=True)
