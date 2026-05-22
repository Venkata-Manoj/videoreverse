"""
VideoReverse Web Interface Error Codes
Standardized error codes for consistent user messaging and troubleshooting.
"""

import os
from enum import Enum
from typing import Dict, Any

# Configuration
MAX_UPLOAD_MB = int(os.environ.get("VIDEO_REV_WEB_MAX_MB", "500"))


class VRLErrorCode(Enum):
    """VideoReverse Web Interface Error Codes"""
    
    # Input Validation Errors (100-199)
    NO_VIDEO_FILE = ("VR-100", "No video file provided")
    UNSUPPORTED_FORMAT = ("VR-101", "Unsupported video format")
    FILE_TOO_LARGE = ("VR-102", "File exceeds maximum size limit")
    INVALID_FILE_PATH = ("VR-103", "Invalid video file path")
    
    # Processing Errors (200-299)
    FFMPEG_NOT_FOUND = ("VR-200", "FFmpeg not found or not accessible")
    VIDEO_ANALYSIS_FAILED = ("VR-201", "Video analysis failed during processing")
    FRAME_EXTRACTION_FAILED = ("VR-202", "Failed to extract frames from video")
    AUDIO_PROCESSING_FAILED = ("VR-203", "Audio processing failed")
    
    # API Errors (300-399)
    GEMINI_API_KEY_MISSING = ("VR-300", "Gemini API key not configured")
    GEMINI_RATE_LIMIT_EXCEEDED = ("VR-301", "Gemini API rate limit exceeded")
    GEMINI_SERVICE_UNAVAILABLE = ("VR-302", "Gemini service temporarily unavailable")
    GEMINI_QUOTA_EXCEEDED = ("VR-303", "Gemini API quota exceeded")
    API_REQUEST_FAILED = ("VR-304", "API request failed")
    
    # System Errors (400-499)
    INTERNAL_PROCESSING_ERROR = ("VR-400", "Internal processing error")
    STORAGE_ACCESS_FAILED = ("VR-401", "Failed to access storage")
    TEMP_FILE_CLEANUP_FAILED = ("VR-402", "Temporary file cleanup failed")
    CONFIGURATION_ERROR = ("VR-403", "Invalid configuration")
    
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
    
    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "code": self.code,
            "message": self.message,
            "category": self.code.split("-")[0]  # VR-XXX -> VR
        }


# Error code to troubleshooting mapping
TROUBLESHOOTING_GUIDE = {
    "VR-100": {
        "title": "No Video File Provided",
        "steps": [
            "Please select a video file to upload",
            "Ensure the file is not empty",
            "Try uploading the file again"
        ],
        "link": "https://github.com/anomalyco/opencode/issues/tagged/error-vr-100"
    },
    "VR-101": {
        "title": "Unsupported Video Format",
        "steps": [
            "Supported formats: MP4, MOV, AVI, MKV, WEBM, M4V",
            "Convert your video to a supported format",
            "Ensure the file extension matches the actual format"
        ],
        "link": "https://github.com/anomalyco/opencode/issues/tagged/error-vr-101"
    },
    "VR-102": {
        "title": "File Too Large",
        "steps": [
            f"Maximum file size is {MAX_UPLOAD_MB}MB",
            "Compress your video using tools like HandBrake",
            "Trim unnecessary parts from the beginning/end",
            "Reduce video resolution or bitrate"
        ],
        "link": "https://github.com/anomalyco/opencode/issues/tagged/error-vr-102"
    },
    "VR-200": {
        "title": "FFmpeg Not Found",
        "steps": [
            "Install FFmpeg on your system",
            "On Ubuntu/Debian: sudo apt-get install ffmpeg",
            "On macOS: brew install ffmpeg",
            "On Windows: Download from https://ffmpeg.org/download.html",
            "Ensure FFmpeg is in your PATH environment variable"
        ],
        "link": "https://github.com/anomalyco/opencode/issues/tagged/error-vr-200"
    },
    "VR-300": {
        "title": "Gemini API Key Missing",
        "steps": [
            "Get a free API key from https://makersuite.google.com/app/apikey",
            "Add it to your .env file: GEMINI_API_KEY=your_key_here",
            "Restart the application after adding the key",
            "Ensure there are no extra spaces in the key"
        ],
        "link": "https://github.com/anomalyco/opencode/issues/tagged/error-vr-300"
    },
    "VR-301": {
        "title": "Gemini Rate Limit Exceeded",
        "steps": [
            "Wait a few minutes before trying again",
            "Enable fallback mode to continue with reduced functionality",
            "Consider upgrading your Gemini API plan",
            "Try processing shorter videos or using highlight mode"
        ],
        "link": "https://github.com/anomalyco/opencode/issues/tagged/error-vr-301"
    },
    "VR-302": {
        "title": "Gemini Service Unavailable",
        "steps": [
            "The Gemini service is temporarily experiencing issues",
            "Wait 5-10 minutes and try again",
            "Check Gemini service status at status.cloud.google.com",
            "Enable fallback mode as a temporary workaround"
        ],
        "link": "https://github.com/anomalyco/opencode/issues/tagged/error-vr-302"
    },
    "VR-400": {
        "title": "Internal Processing Error",
        "steps": [
            "This is an unexpected error - please report it",
            "Include the full error message and steps to reproduce",
            "Try processing a different video to isolate the issue",
            "Check the application logs for more details"
        ],
        "link": "https://github.com/anomalyco/opencode/issues/tagged/error-vr-400"
    }
}

def get_error_details(error_code: VRLErrorCode) -> Dict[str, Any]:
    """Get detailed error information including troubleshooting guide"""
    base_info = error_code.to_dict()
    troubleshooting = TROUBLESHOOTING_GUIDE.get(error_code.code, {
        "title": "Unknown Error",
        "steps": ["Please try again or contact support"],
        "link": "https://github.com/anomalyco/opencode/issues"
    })
    
    return {
        **base_info,
        "troubleshooting": troubleshooting
    }


def format_user_friendly_error(error_code: VRLErrorCode, details: str = None) -> str:
    """Format error for display to end user"""
    base_message = f"{error_code.code}: {error_code.message}"
    if details:
        base_message += f" - {details}"
    return base_message