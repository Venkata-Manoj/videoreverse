from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Any

_limits_cache: dict[str, dict[str, int]] | None = None
_rpm_windows: dict[str, deque[float]] = {}
_tpm_windows: dict[str, deque[float]] = {}
_tpm_tokens: dict[str, deque[int]] = {}
_rpd_windows: dict[str, deque[float]] = {}
_lock: asyncio.Lock | None = None


def _get_limits() -> dict[str, dict[str, int]]:
    global _limits_cache
    if _limits_cache is None:
        path = Path(__file__).resolve().parent.parent / "config" / "model_limits.json"
        if path.exists():
            with open(path) as f:
                _limits_cache = json.load(f)
        else:
            _limits_cache = {}
    return _limits_cache


def get_model_limits(model: str) -> dict[str, int]:
    limits = _get_limits()
    return limits.get(model, {"rpm": 5, "tpm": 250000, "rpd": 1500})


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


def _estimate_tokens(prompt: str, timeline_frames: list[dict], video_duration: float) -> int:
    text_tokens = len(prompt) // 4
    frame_tokens = len(timeline_frames) * 258
    video_tokens = int(video_duration * 300)
    return text_tokens + frame_tokens + video_tokens


def _clean_windows(window: deque, max_age: float) -> None:
    cutoff = time.monotonic() - max_age
    while window and window[0] < cutoff:
        window.popleft()


def _clean_tpm_windows(model: str) -> None:
    cutoff = time.monotonic() - 60
    w = _tpm_windows.get(model)
    t = _tpm_tokens.get(model)
    if w and t:
        while w and w[0] < cutoff:
            w.popleft()
            t.popleft()


def _clean_rpd_window(model: str) -> None:
    cutoff = time.monotonic() - 86400
    w = _rpd_windows.get(model)
    if w:
        while w and w[0] < cutoff:
            w.popleft()


async def wait_for_capacity(
    model: str,
    prompt: str = "",
    timeline_frames: list[dict] | None = None,
    video_duration: float = 0,
    overrides: dict[str, int] | None = None,
) -> dict[str, Any]:
    limits = get_model_limits(model)
    if overrides:
        limits = {**limits, **overrides}

    rpm = limits.get("rpm", 5)
    tpm = limits.get("tpm", 250000)
    rpd = limits.get("rpd", 1500)

    if model not in _rpm_windows:
        _rpm_windows[model] = deque()
    if model not in _tpm_windows:
        _tpm_windows[model] = deque()
        _tpm_tokens[model] = deque()
    if model not in _rpd_windows:
        _rpd_windows[model] = deque()

    lock = _get_lock()
    async with lock:
        _clean_windows(_rpm_windows[model], 60)
        _clean_tpm_windows(model)
        _clean_rpd_window(model)

        now = time.monotonic()

        rpm_count = len(_rpm_windows[model])
        tpm_count = sum(_tpm_tokens.get(model, []))
        rpd_count = len(_rpd_windows[model])

        estimated_tokens = _estimate_tokens(prompt, timeline_frames or [], video_duration)
        print(f"   → Rate state: {rpm_count}/{rpm} RPM | {tpm_count}/{tpm} TPM | {rpd_count}/{rpd} RPD | ~{estimated_tokens} est. tokens", flush=True)

        delays: list[float] = []

        if rpm_count >= rpm:
            wait = _rpm_windows[model][0] + 60 - now
            if wait > 0:
                delays.append(wait)

        if tpm_count > 0 and tpm_count + estimated_tokens > tpm:
            oldest_tok = _tpm_windows[model][0]
            wait = oldest_tok + 60 - now
            if wait > 0:
                delays.append(wait)

        if rpd_count >= rpd:
            wait = _rpd_windows[model][0] + 86400 - now
            if wait > 0:
                delays.append(wait)

        if delays:
            wait_time = max(delays) + 1
            print(f"   → Rate limited: waiting {wait_time:.0f}s (RPM:{rpm_count}/{rpm} TPM:{tpm_count}/{tpm} RPD:{rpd_count}/{rpd})", flush=True)
            await asyncio.sleep(wait_time)

        _clean_windows(_rpm_windows[model], 60)
        _clean_tpm_windows(model)
        _clean_rpd_window(model)

        _rpm_windows[model].append(time.monotonic())
        _tpm_windows[model].append(time.monotonic())
        _tpm_tokens[model].append(estimated_tokens)
        _rpd_windows[model].append(time.monotonic())

        return {
            "estimated_tokens": estimated_tokens,
            "rpm_remaining": rpm - len(_rpm_windows[model]),
            "rpd_remaining": rpd - len(_rpd_windows[model]),
        }
