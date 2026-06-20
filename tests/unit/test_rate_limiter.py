from __future__ import annotations

import asyncio
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from utils.rate_limiter import (
    _clean_windows,
    _estimate_tokens,
    _rpd_windows,
    _rpm_windows,
    _tpm_tokens,
    _tpm_windows,
    get_model_limits,
    wait_for_capacity,
)


def test_get_model_limits_known_model():
    limits = get_model_limits("gemini-2.5-flash")
    assert "rpm" in limits
    assert "tpm" in limits
    assert "rpd" in limits
    assert limits["rpm"] > 0


def test_get_model_limits_unknown_model():
    limits = get_model_limits("nonexistent-model-xyz")
    assert limits == {"rpm": 5, "tpm": 250000, "rpd": 1500}


def test_estimate_tokens_text_only():
    tokens = _estimate_tokens("hello world", [], 0)
    assert tokens == len("hello world") // 4


def test_estimate_tokens_with_frames():
    frames = [{"index": 0}, {"index": 1}]
    tokens = _estimate_tokens("", frames, 0)
    assert tokens == 2 * 258


def test_estimate_tokens_with_duration():
    tokens = _estimate_tokens("", [], 10.0)
    assert tokens == int(10.0 * 300)


def test_estimate_tokens_combined():
    tokens = _estimate_tokens("test", [{"i": 0}], 5.0)
    expected = len("test") // 4 + 258 + int(5.0 * 300)
    assert tokens == expected


def test_clean_windows_removes_old_entries():
    window: deque[float] = deque()
    now = time.monotonic()
    window.append(now - 120)
    window.append(now - 30)
    window.append(now)
    _clean_windows(window, 60)
    assert len(window) == 2
    assert window[0] == now - 30


def test_clean_windows_keeps_all_recent():
    now = time.monotonic()
    window: deque[float] = deque([now - 10, now - 20, now - 30])
    _clean_windows(window, 60)
    assert len(window) == 3


def test_clean_windows_empty():
    window: deque[float] = deque()
    _clean_windows(window, 60)
    assert len(window) == 0


def test_rpm_tracking():
    _rpm_windows.clear()
    _tpm_windows.clear()
    _tpm_tokens.clear()
    _rpd_windows.clear()

    async def run():
        result = await wait_for_capacity("test-model-rpm", "hello", [], 0, {"rpm": 100, "tpm": 999999, "rpd": 999999})
        assert result["estimated_tokens"] > 0
        assert result["rpm_remaining"] >= 0
        assert result["rpd_remaining"] >= 0

    asyncio.run(run())


def test_rate_limit_tracks_requests():
    _rpm_windows.clear()
    _tpm_windows.clear()
    _tpm_tokens.clear()
    _rpd_windows.clear()

    async def run():
        model = "test-model-rpm-track"
        overrides = {"rpm": 100, "tpm": 999999, "rpd": 999999}
        r1 = await wait_for_capacity(model, "test", [], 0, overrides)
        r2 = await wait_for_capacity(model, "test", [], 0, overrides)
        assert r1["estimated_tokens"] > 0
        assert r2["estimated_tokens"] > 0
        assert r2["rpm_remaining"] <= r1["rpm_remaining"]

    asyncio.run(run())


def test_rpd_tracking():
    _rpm_windows.clear()
    _tpm_windows.clear()
    _tpm_tokens.clear()
    _rpd_windows.clear()

    async def run():
        model = "test-model-rpd"
        overrides = {"rpm": 100, "tpm": 999999, "rpd": 10}
        r1 = await wait_for_capacity(model, "", [], 0, overrides)
        r2 = await wait_for_capacity(model, "", [], 0, overrides)
        assert r2["rpd_remaining"] <= r1["rpd_remaining"]

    asyncio.run(run())


def test_empty_model_uses_defaults():
    limits = get_model_limits("")
    assert limits["rpm"] == 5


def test_clean_windows_exact_boundary():
    now = time.monotonic()
    window: deque[float] = deque([now - 60, now - 60 + 0.001])
    _clean_windows(window, 60)
    assert len(window) == 1
