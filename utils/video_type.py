from __future__ import annotations

from typing import Any

VIDEO_TYPES: dict[str, str] = {
    "CGI": "cgi",
    "LIVE_ACTION": "live-action",
    "ANIMATION": "animation",
    "SCREEN": "screen",
    "DRONE": "drone",
    "SOCIAL": "social",
    "UNKNOWN": "unknown",
}


def detect_video_type(
    metadata: dict[str, Any] | None = None,
    extraction: dict[str, Any] | None = None,
) -> str:
    dims = ""
    if metadata and metadata.get("width") and metadata.get("height"):
        dims = f"{metadata['width']}x{metadata['height']}"
    codec = metadata.get("codec", "") if metadata else ""
    motion_level = extraction.get("motion_signal_level", "unknown") if extraction else "unknown"

    codec_lower = codec.lower()
    if ("h264" in codec_lower or "hevc" in codec_lower) and dims in ("1920x1080", "3840x2160"):
        if motion_level in ("medium", "high"):
            return VIDEO_TYPES["LIVE_ACTION"]
        return VIDEO_TYPES["DRONE"]

    if "png" in codec_lower or "animation" in codec_lower:
        return VIDEO_TYPES["ANIMATION"]

    if "720" in dims and motion_level == "low":
        return VIDEO_TYPES["SCREEN"]

    if ("1080" in dims or "720" in dims) and motion_level == "low":
        return VIDEO_TYPES["SCREEN"]

    import re

    vertical_pattern = re.match(r"(\d+)x(\d+)", dims)
    if vertical_pattern:
        w, h = int(vertical_pattern.group(1)), int(vertical_pattern.group(2))
        if h > w:
            return VIDEO_TYPES["SOCIAL"]

    if motion_level == "high":
        return VIDEO_TYPES["CGI"]

    return VIDEO_TYPES["UNKNOWN"]


def get_video_type_label(video_type: str | None) -> str:
    labels = {
        VIDEO_TYPES["CGI"]: "CGI / 3D Animation",
        VIDEO_TYPES["LIVE_ACTION"]: "Live-Action Footage",
        VIDEO_TYPES["ANIMATION"]: "2D Animation / Anime",
        VIDEO_TYPES["SCREEN"]: "Screen Recording / Tutorial",
        VIDEO_TYPES["DRONE"]: "Drone / Aerial Footage",
        VIDEO_TYPES["SOCIAL"]: "Social Media (Vertical)",
        VIDEO_TYPES["UNKNOWN"]: "Unknown Video Type",
    }
    return labels.get(video_type, "Unknown")
