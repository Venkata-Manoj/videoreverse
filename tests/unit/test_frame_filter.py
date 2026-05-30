from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import numpy as np
import pytest

from utils.frame_filter import filter_blurry_frames, score_blur


def _make_test_image(path: str, width: int = 200, height: int = 200, blur_kernel: int = 0) -> None:
    """Create a test image. blur_kernel=0 = sharp noise; blur_kernel>0 = Gaussian blur."""
    np.random.seed(0)
    pixels = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    if blur_kernel > 0:
        import cv2

        pixels = cv2.GaussianBlur(pixels, (blur_kernel, blur_kernel), 0)
    import cv2

    cv2.imwrite(path, pixels)


def test_score_blur_sharp() -> None:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        _make_test_image(path, blur_kernel=0)
        score = score_blur(path)
        assert score is not None
        assert score > 50
    finally:
        os.unlink(path)


def test_score_blur_blurry() -> None:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        _make_test_image(path, blur_kernel=15)
        score = score_blur(path)
        assert score is not None
        # Blurry image score should be well below sharp image (~1.2M)
        assert score < 500
    finally:
        os.unlink(path)


def test_filter_mixed() -> None:
    with tempfile.TemporaryDirectory() as d:
        sharp_a = os.path.join(d, "sharp_a.jpg")
        sharp_b = os.path.join(d, "sharp_b.jpg")
        blurry_path = os.path.join(d, "blurry.jpg")
        _make_test_image(sharp_a, blur_kernel=0)
        _make_test_image(sharp_b, blur_kernel=0)
        _make_test_image(blurry_path, blur_kernel=35)
        frames = [
            {"index": 0, "path": sharp_a, "motion_level": "low"},
            {"index": 1, "path": sharp_b, "motion_level": "low"},
            {"index": 2, "path": blurry_path, "motion_level": "low"},
        ]
        result = filter_blurry_frames(frames, threshold=50)
        assert len(result) == 2
        assert all(f["index"] in (0, 1) for f in result)
        assert all("blur_score" in f for f in result)


def test_filter_preserves_high_motion() -> None:
    with tempfile.TemporaryDirectory() as d:
        blurry_high = os.path.join(d, "blurry_high.jpg")
        _make_test_image(blurry_high, blur_kernel=15)
        frames = [
            {"index": 0, "path": blurry_high, "motion_level": "high"},
        ]
        result = filter_blurry_frames(frames, threshold=100)
        assert len(result) == 1


def test_filter_empty_safety() -> None:
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for i in range(3):
            p = os.path.join(d, f"blurry_{i}.jpg")
            _make_test_image(p, blur_kernel=25)
            paths.append(p)
        frames = [
            {"index": i, "path": p, "motion_level": "low"}
            for i, p in enumerate(paths)
        ]
        result = filter_blurry_frames(frames, threshold=500)
        # All should be restored (safety guard)
        assert len(result) == 3


def test_filter_enriches_metadata() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.jpg")
        _make_test_image(path, blur_kernel=0)
        frames = [{"index": 0, "path": path, "motion_level": "low"}]
        result = filter_blurry_frames(frames, threshold=100)
        assert "blur_score" in result[0]
        assert isinstance(result[0]["blur_score"], float)


def test_filter_no_cv2_fallback() -> None:
    frames = [{"index": 0, "path": "/nonexistent.jpg", "motion_level": "low"}]
    with patch("utils.frame_filter._HAS_CV2", False):
        result = filter_blurry_frames(frames, threshold=100)
    assert len(result) == 1


def test_filter_threshold_zero() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.jpg")
        _make_test_image(path, blur_kernel=15)
        frames = [{"index": 0, "path": path, "motion_level": "low"}]
        result = filter_blurry_frames(frames, threshold=0)
        assert len(result) == 1


def test_aggressive_filter_drops_transient() -> None:
    with tempfile.TemporaryDirectory() as d:
        sharp_a = os.path.join(d, "sharp_a.jpg")
        blurry_mid = os.path.join(d, "blurry_mid.jpg")
        sharp_b = os.path.join(d, "sharp_b.jpg")
        _make_test_image(sharp_a, blur_kernel=0)
        _make_test_image(blurry_mid, blur_kernel=15)
        _make_test_image(sharp_b, blur_kernel=0)
        frames = [
            {"index": 0, "path": sharp_a, "motion_level": "high"},
            {"index": 1, "path": blurry_mid, "motion_level": "high"},
            {"index": 2, "path": sharp_b, "motion_level": "high"},
        ]
        non_aggressive = filter_blurry_frames(frames, threshold=500, aggressive=False)
        aggressive = filter_blurry_frames(frames, threshold=500, aggressive=True)
        assert len(non_aggressive) == 3
        assert len(aggressive) == 2
        assert all(f["index"] in (0, 2) for f in aggressive)


def test_aggressive_filter_edge_no_left() -> None:
    with tempfile.TemporaryDirectory() as d:
        blurry = os.path.join(d, "blurry.jpg")
        sharp = os.path.join(d, "sharp.jpg")
        _make_test_image(blurry, blur_kernel=15)
        _make_test_image(sharp, blur_kernel=0)
        frames = [
            {"index": 0, "path": blurry, "motion_level": "high"},
            {"index": 1, "path": sharp, "motion_level": "low"},
        ]
        result = filter_blurry_frames(frames, threshold=500, aggressive=True)
        assert len(result) == 2


def test_score_blur_nonexistent_file() -> None:
    score = score_blur("/nonexistent/image.jpg")
    assert score is None
