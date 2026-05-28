from __future__ import annotations

from enum import Enum
from typing import Any


class VRErrorCode(Enum):
    MISSING_VIDEO_PATH = ("VR-001", "No video path provided")
    INVALID_MODEL = ("VR-002", "Unsupported model specified")
    INVALID_ARGUMENT = ("VR-003", "Invalid CLI argument or option")
    FILE_NOT_FOUND = ("VR-004", "Video file not found or inaccessible")
    PATH_RESOLUTION_FAILED = ("VR-005", "Failed to resolve video path")
    URL_DOWNLOAD_FAILED = ("VR-006", "Failed to download video from URL")
    INVALID_FORMAT = ("VR-007", "Invalid output format specified")

    FFMPEG_NOT_FOUND = ("VR-101", "FFmpeg not found on system PATH")
    FFPROBE_FAILED = ("VR-102", "FFprobe failed to read video metadata")
    FRAME_EXTRACTION_FAILED = ("VR-103", "FFmpeg keyframe extraction failed")
    AUDIO_EXTRACTION_FAILED = ("VR-104", "FFmpeg audio extraction failed")
    TRANSCRIPTION_FAILED = ("VR-105", "Whisper transcription failed")
    SAMPLING_FAILED = ("VR-106", "Smart frame sampling failed")
    VIDEO_CORRUPT = ("VR-107", "Video file appears corrupt or unreadable")
    UNSUPPORTED_CODEC = ("VR-108", "Video codec not supported by ffmpeg")

    GEMINI_KEY_MISSING = ("VR-201", "GEMINI_API_KEY environment variable not set")
    GEMINI_FILE_UPLOAD_FAILED = ("VR-202", "Gemini File API upload failed")
    GEMINI_SYNTHESIS_FAILED = ("VR-203", "Gemini blueprint synthesis failed")
    GEMINI_RATE_LIMITED = ("VR-204", "Gemini API rate limit exceeded")
    GEMINI_SERVICE_DOWN = ("VR-205", "Gemini service temporarily unavailable")
    GEMINI_QUOTA_EXCEEDED = ("VR-206", "Gemini API quota exhausted")
    GEMINI_INVALID_RESPONSE = ("VR-207", "Gemini returned invalid or malformed response")

    COMPILATION_FAILED = ("VR-301", "Prompt compilation failed")
    BLUEPRINT_VALIDATION_FAILED = ("VR-302", "Blueprint validation failed")
    CACHE_READ_FAILED = ("VR-304", "Failed to read cached blueprint")
    CACHE_WRITE_FAILED = ("VR-305", "Failed to write blueprint to cache")

    OUTPUT_DIR_CREATE_FAILED = ("VR-401", "Failed to create output directory")
    OUTPUT_WRITE_FAILED = ("VR-402", "Failed to write output file")
    TEMP_FILE_CLEANUP_FAILED = ("VR-403", "Temporary file cleanup failed")
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
        super().__init__(" -- ".join(messages))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "cause": str(self.cause) if self.cause else None,
        }


def format_error(code: VRErrorCode, detail: str | None = None) -> str:
    msg = f"[{code.code}] {code.message}"
    if detail:
        msg += f" -- {detail}"
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
        ("download", VRErrorCode.URL_DOWNLOAD_FAILED),
        ("yt-dlp", VRErrorCode.URL_DOWNLOAD_FAILED),
        ("url", VRErrorCode.URL_DOWNLOAD_FAILED),
        ("corrupt", VRErrorCode.VIDEO_CORRUPT),
        ("validation", VRErrorCode.BLUEPRINT_VALIDATION_FAILED),
        ("cache", VRErrorCode.CACHE_READ_FAILED),
        ("cleanup", VRErrorCode.TEMP_FILE_CLEANUP_FAILED),
    ]
    for pattern, code in checks:
        if pattern in err_str:
            return code
    return None
