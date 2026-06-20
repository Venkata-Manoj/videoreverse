from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.synthesize import _detect_motion_transitions, _extract_motion_transitions
from tests.unit.test_framework import describe, expect, it


def _frame(
    index: int,
    motion_level: str = "medium",
    timestamp: float = 0.0,
) -> dict[str, Any]:
    return {"index": index, "motion_level": motion_level, "timestamp_seconds": timestamp}


def run_tests():
    describe("_detect_motion_transitions", _test_detect_empty)
    describe("_detect_motion_transitions", _test_detect_too_few)
    describe("_detect_motion_transitions", _test_detect_no_transition)
    describe("_detect_motion_transitions", _test_detect_low_to_high)
    describe("_detect_motion_transitions", _test_detect_high_to_low)
    describe("_detect_motion_transitions", _test_detect_multiple)
    describe("_detect_motion_transitions", _test_detect_missing_motion)
    describe("_detect_motion_transitions", _test_detect_all_high)
    describe("_detect_motion_transitions", _test_detect_medium_edges)
    describe("_detect_motion_transitions", _test_detect_low_high_low_high)
    describe("_extract_motion_transitions", _test_extract_none)
    describe("_extract_motion_transitions", _test_extract_empty)
    describe("_extract_motion_transitions", _test_extract_normal)
    describe("_extract_motion_transitions", _test_extract_no_transition)
    describe("_extract_motion_transitions", _test_extract_matches_detect)


def _test_detect_empty() -> None:
    def _f() -> None:
        expect(_detect_motion_transitions([])).to_be([])
    it("returns empty list for empty input", _f)


def _test_detect_too_few() -> None:
    def _single() -> None:
        expect(_detect_motion_transitions([_frame(0)])).to_be([])
    it("returns empty for single frame", _single)

    def _two() -> None:
        expect(_detect_motion_transitions([_frame(0), _frame(1)])).to_be([])
    it("returns empty for two frames", _two)


def _test_detect_no_transition() -> None:
    def _f() -> None:
        expect(_detect_motion_transitions([
            _frame(0, "low", 0.0),
            _frame(1, "low", 1.0),
            _frame(2, "low", 2.0),
            _frame(3, "low", 3.0),
        ])).to_be([])
    it("returns empty when all frames same motion", _f)


def _test_detect_low_to_high() -> None:
    def _count() -> None:
        expect(len(_detect_motion_transitions([
            _frame(0, "low", 0.0),
            _frame(1, "high", 1.0),
            _frame(2, "high", 2.0),
        ]))).to_be(1)
    it("detects low to high transition", _count)

    def _details() -> None:
        transitions = _detect_motion_transitions([
            _frame(0, "low", 0.0),
            _frame(1, "high", 1.5),
            _frame(2, "high", 3.0),
        ])
        expect(len(transitions)).to_be(1)
        expect(transitions[0]["frame_index"]).to_be(1)
        expect(transitions[0]["timestamp"]).to_be(1.5)
        expect(transitions[0]["type"]).to_be("motion_shift")
    it("reports correct frame_index and timestamp", _details)


def _test_detect_high_to_low() -> None:
    def _f() -> None:
        expect(len(_detect_motion_transitions([
            _frame(0, "high", 0.0),
            _frame(1, "low", 1.0),
            _frame(2, "low", 2.0),
        ]))).to_be(1)
    it("detects high to low transition", _f)


def _test_detect_multiple() -> None:
    def _f() -> None:
        transitions = _detect_motion_transitions([
            _frame(0, "low", 0.0),
            _frame(1, "high", 1.0),
            _frame(2, "high", 2.0),
            _frame(3, "low", 3.0),
            _frame(4, "low", 4.0),
        ])
        expect(len(transitions) >= 2).to_be(True)
        expect(transitions[0]["frame_index"]).to_be(1)
        expect(transitions[-1]["frame_index"]).to_be(3)
    it("detects multiple transitions", _f)


def _test_detect_low_high_low_high() -> None:
    def _f() -> None:
        transitions = _detect_motion_transitions([
            _frame(0, "low", 0.0),
            _frame(1, "high", 1.0),
            _frame(2, "low", 2.0),
            _frame(3, "high", 3.0),
            _frame(4, "low", 4.0),
        ])
        expect(len(transitions) >= 2).to_be(True)
    it("detects transitions in alternating pattern", _f)


def _test_detect_missing_motion() -> None:
    def _f() -> None:
        transitions = _detect_motion_transitions([
            _frame(0, "low", 0.0),
            {"index": 1, "timestamp_seconds": 1.0},
            _frame(2, "low", 2.0),
        ])
        expect(len(transitions)).to_be(0)
    it("treats missing motion_level as medium", _f)


def _test_detect_all_high() -> None:
    def _f() -> None:
        expect(_detect_motion_transitions([
            _frame(0, "high", 0.0),
            _frame(1, "high", 0.5),
            _frame(2, "high", 1.0),
        ])).to_be([])
    it("returns empty when all frames are high motion", _f)


def _test_detect_medium_edges() -> None:
    def _low_to_medium() -> None:
        expect(len(_detect_motion_transitions([
            _frame(0, "low", 0.0),
            _frame(1, "medium", 1.0),
            _frame(2, "medium", 2.0),
        ]))).to_be(0)
    it("low to medium is not a transition (diff=1)", _low_to_medium)

    def _medium_to_high() -> None:
        expect(len(_detect_motion_transitions([
            _frame(0, "medium", 0.0),
            _frame(1, "high", 1.0),
            _frame(2, "high", 2.0),
        ]))).to_be(0)
    it("medium to high is not a transition (diff=1)", _medium_to_high)


def _test_extract_none() -> None:
    def _f() -> None:
        expect(_extract_motion_transitions(None)).to_be(None)
    it("returns None for None input", _f)


def _test_extract_empty() -> None:
    def _f() -> None:
        expect(_extract_motion_transitions([])).to_be(None)
    it("returns None for empty list", _f)

    def _g() -> None:
        expect(_extract_motion_transitions([_frame(0), _frame(1)])).to_be(None)
    it("returns None for too-few frames", _g)


def _test_extract_normal() -> None:
    def _f() -> None:
        result = _extract_motion_transitions([
            _frame(0, "low", 0.0),
            _frame(1, "high", 1.0),
            _frame(2, "high", 2.0),
        ])
        expect(result is not None).to_be(True)
        expect("1.0s" in result).to_be(True)
        expect("frame 1" in result).to_be(True)
    it("formats transitions as comma-separated string", _f)


def _test_extract_no_transition() -> None:
    def _f() -> None:
        expect(_extract_motion_transitions([
            _frame(0, "low", 0.0),
            _frame(1, "low", 1.0),
            _frame(2, "low", 2.0),
        ])).to_be(None)
    it("returns None when no transitions", _f)


def _test_extract_matches_detect() -> None:
    def _f() -> None:
        frames = [
            _frame(0, "low", 0.0),
            _frame(1, "high", 1.0),
            _frame(2, "low", 2.0),
        ]
        detect_result = _detect_motion_transitions(frames)
        extract_result = _extract_motion_transitions(frames)
        expect(len(detect_result) > 0).to_be(True)
        expect(extract_result is not None).to_be(True)
        expect(extract_result.count("s (frame")).to_be(len(detect_result))
    it("extract matches detect output count", _f)
