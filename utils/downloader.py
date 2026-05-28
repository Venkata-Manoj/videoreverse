from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from utils.error_codes import VRError, VRErrorCode


URL_REGEX = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def is_valid_video_url(url: str) -> bool:
    return bool(URL_REGEX.match(url.strip()))


def download_video(url: str, dest_dir: str, max_mb: int = 500) -> str:
    if not is_valid_video_url(url):
        raise VRError(
            VRErrorCode.URL_DOWNLOAD_FAILED,
            detail=f"Invalid URL: {url}",
        )

    try:
        import yt_dlp
    except ImportError:
        raise VRError(
            VRErrorCode.URL_DOWNLOAD_FAILED,
            detail="yt-dlp is not installed. Run: pip install yt-dlp",
        )

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    outtmpl = str(dest / f"{uuid.uuid4().hex}.%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "max_filesize": max_mb * 1024 * 1024,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError as e:
        raise VRError(
            VRErrorCode.URL_DOWNLOAD_FAILED,
            detail=f"Download failed: {e}",
        )

    actual = str(dest / Path(filename).name)
    actual = actual.rsplit(".", 1)[0] + "." + (info.get("ext") or "mp4")

    for candidate in dest.glob(f"{Path(outtmpl).stem.split('.')[0]}*"):
        if candidate.stat().st_size > 0:
            actual = str(candidate)
            break

    if not os.path.isfile(actual) or os.path.getsize(actual) == 0:
        raise VRError(
            VRErrorCode.URL_DOWNLOAD_FAILED,
            detail="Downloaded file is empty or missing",
        )

    return actual
