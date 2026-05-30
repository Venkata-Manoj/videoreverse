from __future__ import annotations

import os
from typing import Any

try:
    import cv2

    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False


def score_blur(image_path: str) -> float | None:
    """
    Laplacian variance normalized by pixel count.
    Higher = sharper. Normalized so threshold ~100 works roughly across resolutions.
    Returns None on read failure or if cv2 unavailable.
    """
    if not _HAS_CV2:
        return None
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    h, w = img.shape
    laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
    score = laplacian_var / (w * h) * 1_000_000
    return score


def _is_motion_blur_transient(scored: list[dict[str, Any]], idx: int, threshold: float) -> bool:
    """Check if a blurry high-motion frame is a transient (fast pan/zoom artifact).
    Returns True if both adjacent frames are significantly sharper."""
    if idx <= 0 or idx >= len(scored) - 1:
        return False
    prev_score = scored[idx - 1].get("blur_score", 0)
    next_score = scored[idx + 1].get("blur_score", 0)
    curr_score = scored[idx].get("blur_score", 0)
    return prev_score >= threshold and next_score >= threshold and curr_score < threshold


def filter_blurry_frames(
    frames: list[dict[str, Any]],
    threshold: float = 100.0,
    aggressive: bool = False,
) -> list[dict[str, Any]]:
    """
    Dual-signal filter:
    - Drop frames that are blurry (score < threshold) AND not high-motion.
    - Safety guard: if filtering leaves < 2 frames, restore originals.
    - Adds `blur_score` to each frame's metadata.
    - Gracefully no-ops if cv2 unavailable (warns once, returns originals).
    - When aggressive=True, also drops blurry high-motion frames that are likely
      transient motion-blur artifacts (both neighbors are sharp).
    """
    if not _HAS_CV2:
        print("   → opencv-python-headless not installed, skipping blur filtering", flush=True)
        return frames

    if threshold <= 0:
        for f in frames:
            f["blur_score"] = 0.0
        return frames

    scored = []
    for f in frames:
        path = f.get("path")
        if path and os.path.exists(path):
            s = score_blur(path)
            f["blur_score"] = s if s is not None else 0.0
        else:
            f["blur_score"] = 0.0
        scored.append(f)

    kept: list[dict[str, Any]] = []
    for i, f in enumerate(scored):
        score = f.get("blur_score", 0)
        is_sharp = score >= threshold
        is_high_motion = f.get("motion_level") == "high"
        is_transient = aggressive and is_high_motion and _is_motion_blur_transient(scored, i, threshold)
        if is_sharp or (is_high_motion and not is_transient):
            kept.append(f)

    if len(kept) < 2:
        print(
            f"   → Only {len(kept)} frame(s) survived blur filter — restoring all {len(scored)} originals",
            flush=True,
        )
        return scored

    return kept
