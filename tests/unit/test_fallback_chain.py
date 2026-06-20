from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _select_frames_impl(timeline_frames: list[dict], max_frames: int = 15) -> list[dict]:
    if not timeline_frames:
        return []
    if len(timeline_frames) <= max_frames:
        return timeline_frames
    step = (len(timeline_frames) - 1) / max_frames
    selected = [timeline_frames[0]]
    for i in range(1, max_frames - 1):
        idx = int(round(i * step))
        selected.append(timeline_frames[idx])
    selected.append(timeline_frames[-1])
    return selected


def _normalize_blueprint_impl(blueprint: dict) -> None:
    if "chronological_shots" not in blueprint and "shots" in blueprint:
        blueprint["chronological_shots"] = blueprint.pop("shots")


def test_select_frames_empty():
    assert _select_frames_impl([]) == []


def test_select_frames_fewer_than_max():
    frames = [{"index": 0}, {"index": 1}, {"index": 2}]
    result = _select_frames_impl(frames, max_frames=5)
    assert len(result) == 3
    assert result == frames


def test_select_frames_exact_max():
    frames = [{"index": i} for i in range(10)]
    result = _select_frames_impl(frames, max_frames=10)
    assert len(result) == 10


def test_select_frames_more_than_max():
    frames = [{"index": i} for i in range(20)]
    result = _select_frames_impl(frames, max_frames=10)
    assert len(result) == 10
    assert result[0] == frames[0]
    assert result[-1] == frames[-1]


def test_select_frames_preserves_first_and_last():
    frames = [{"index": i} for i in range(30)]
    result = _select_frames_impl(frames, max_frames=5)
    assert result[0]["index"] == 0
    assert result[-1]["index"] == 29


def test_select_frames_evenly_spread():
    frames = [{"index": i} for i in range(10)]
    result = _select_frames_impl(frames, max_frames=3)
    assert len(result) == 3
    assert result[0]["index"] == 0
    assert result[-1]["index"] == 9


def test_select_frames_single_frame():
    frames = [{"index": 0}]
    result = _select_frames_impl(frames, max_frames=10)
    assert len(result) == 1
    assert result[0]["index"] == 0


def test_select_frames_two_frames():
    frames = [{"index": 0}, {"index": 1}]
    result = _select_frames_impl(frames, max_frames=10)
    assert len(result) == 2


def test_normalize_blueprint_shots_key():
    blueprint = {
        "global_aesthetic": {},
        "shots": [{"shot_index": 0}],
    }
    _normalize_blueprint_impl(blueprint)
    assert "chronological_shots" in blueprint
    assert "shots" not in blueprint
    assert len(blueprint["chronological_shots"]) == 1


def test_normalize_blueprint_already_has_chronological():
    blueprint = {
        "global_aesthetic": {},
        "chronological_shots": [{"shot_index": 0}],
    }
    _normalize_blueprint_impl(blueprint)
    assert "chronological_shots" in blueprint
    assert len(blueprint["chronological_shots"]) == 1


def test_select_frames_large_gap():
    frames = [{"index": 0}] + [{"index": i} for i in range(1, 50)]
    result = _select_frames_impl(frames, max_frames=5)
    assert len(result) == 5
    assert result[0]["index"] == 0
    assert result[-1]["index"] == 49
