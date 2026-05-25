from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.compile import get_template_version
from utils.cli import parse_cli_args
from utils.versioning import (
    _sanitize_video_name,
    get_next_version,
    list_versions,
    load_history,
    save_history,
)
from tests.unit.test_framework import describe, it, expect

MOCK_OUTPUT = {
    "video_metadata": {"filename": "test_video.mp4", "duration_seconds": 30.0},
    "blueprint": {
        "global_aesthetic": {"art_style": "cinematic", "color_grading": "warm", "lighting_setup": "natural"},
        "chronological_shots": [
            {
                "shot_index": 0,
                "start_time_seconds": 0,
                "end_time_seconds": 5,
                "duration_seconds": 5,
                "camera_direction": "static",
                "framing_type": "wide",
                "action_and_motion": "walking",
                "environment_context": "forest",
                "negative_elements": [],
                "frame_references": [],
            },
        ],
    },
    "prompts": {
        "runway_gen4_5": {
            "label": "Runway Gen-4.5",
            "shots": [{"shot_index": 0, "prompt": "test prompt"}],
        },
    },
    "_meta": {
        "video_type": "live-action",
        "fallback_active": False,
        "fallback_reason": None,
        "template_version": "1.0",
    },
}


def run_tests():
    describe("_sanitize_video_name", _test_sanitize_name)
    describe("get_template_version", _test_get_template_version)
    describe("save_history / load_history", _test_save_load)
    describe("get_next_version", _test_next_version)
    describe("list_versions", _test_list_versions)
    describe("parse_cli_args --rollback", _test_cli_rollback)
    describe("parse_cli_args --list-versions", _test_cli_list_versions)


def _test_sanitize_name() -> None:
    def _extracts_basename() -> None:
        expect(_sanitize_video_name("/path/to/video.mp4")).to_equal("video")
    it("extracts basename without extension", _extracts_basename)

    def _handles_windows_path() -> None:
        expect(_sanitize_video_name("E:\\videos\\test.mp4")).to_equal("test")
    it("handles Windows paths", _handles_windows_path)

    def _replaces_special_chars() -> None:
        expect(_sanitize_video_name("my cool video!@#.mp4")).to_equal("my_cool_video")
    it("replaces and strips trailing underscores", _replaces_special_chars)

    def _unknown_for_empty() -> None:
        name = _sanitize_video_name("")
        expect(name).to_equal("unknown")
    it("returns unknown for empty path", _unknown_for_empty)


def _test_get_template_version() -> None:
    def _returns_string() -> None:
        version = get_template_version()
        expect(isinstance(version, str)).to_be(True)
        expect(len(version)).to_be_greater_than(0)
    it("returns a non-empty string", _returns_string)

    def _returns_semver() -> None:
        version = get_template_version()
        parts = version.split(".")
        expect(len(parts)).to_be(2)
    it("returns a semver-like string (X.Y)", _returns_semver)


def _test_save_load() -> None:
    def _save_and_load_roundtrip() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            version = save_history(MOCK_OUTPUT, "test_video.mp4", tmp)
            expect(version).to_be(1)
            loaded = load_history("test_video.mp4", tmp, 1)
            assert loaded is not None
            expect(loaded["video_metadata"]["filename"]).to_equal("test_video.mp4")
            expect(loaded["_meta"]["history_version"]).to_be(1)
            expect(loaded["_meta"]["template_version"]).to_equal("1.0")
            assert "history_saved_at" in loaded["_meta"]
    it("saves and loads a version roundtrip", _save_and_load_roundtrip)

    def _load_nonexistent_returns_none() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = load_history("nonexistent.mp4", tmp, 99)
            expect(result).to_be(None)
    it("returns None for nonexistent version", _load_nonexistent_returns_none)

    def _save_multiple_increments_version() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            v1 = save_history(MOCK_OUTPUT, "test_video.mp4", tmp)
            v2 = save_history(MOCK_OUTPUT, "test_video.mp4", tmp)
            v3 = save_history(MOCK_OUTPUT, "test_video.mp4", tmp)
            expect(v1).to_be(1)
            expect(v2).to_be(2)
            expect(v3).to_be(3)
    it("increments version on consecutive saves", _save_multiple_increments_version)

    def _preserves_all_data() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_history(MOCK_OUTPUT, "test_video.mp4", tmp)
            loaded = load_history("test_video.mp4", tmp, 1)
            assert loaded is not None
            expect(loaded["blueprint"]["global_aesthetic"]["art_style"]).to_equal("cinematic")
            expect(loaded["prompts"]["runway_gen4_5"]["shots"][0]["prompt"]).to_equal("test prompt")
    it("preserves blueprint and prompts data", _preserves_all_data)


def _test_next_version() -> None:
    def _empty_dir_returns_1() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expect(get_next_version("test.mp4", tmp)).to_be(1)
    it("returns 1 when history is empty", _empty_dir_returns_1)

    def _after_saves_returns_next() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_history(MOCK_OUTPUT, "video.mp4", tmp)
            expect(get_next_version("video.mp4", tmp)).to_be(2)
    it("returns n+1 after n saves", _after_saves_returns_next)

    def _different_videos_independent() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_history(MOCK_OUTPUT, "video_a.mp4", tmp)
            save_history(MOCK_OUTPUT, "video_a.mp4", tmp)
            save_history(MOCK_OUTPUT, "video_b.mp4", tmp)
            expect(get_next_version("video_a.mp4", tmp)).to_be(3)
            expect(get_next_version("video_b.mp4", tmp)).to_be(2)
    it("tracks versions independently per video", _different_videos_independent)

    def _missing_history_dir() -> None:
        expect(get_next_version("video.mp4", "/nonexistent/dir")).to_be(1)
    it("returns 1 when history dir does not exist", _missing_history_dir)


def _test_list_versions() -> None:
    def _empty_dir() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vlist = list_versions("video.mp4", tmp)
            expect(vlist).to_equal([])
    it("returns empty list for no history", _empty_dir)

    def _lists_saved_versions() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_history(MOCK_OUTPUT, "video.mp4", tmp)
            save_history(MOCK_OUTPUT, "video.mp4", tmp)
            vlist = list_versions("video.mp4", tmp)
            expect(len(vlist)).to_be(2)
            expect(vlist[0]["version"]).to_be(1)
            expect(vlist[1]["version"]).to_be(2)
    it("lists all saved versions in order", _lists_saved_versions)

    def _includes_metadata() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_history(MOCK_OUTPUT, "video.mp4", tmp)
            vlist = list_versions("video.mp4", tmp)
            assert len(vlist) == 1
            expect("version" in vlist[0]).to_be(True)
            expect("template_version" in vlist[0]).to_be(True)
            expect("saved_at" in vlist[0]).to_be(True)
            expect("fallback_active" in vlist[0]).to_be(True)
            expect("shots" in vlist[0]).to_be(True)
            expect("models" in vlist[0]).to_be(True)
    it("includes metadata in each entry", _includes_metadata)

    def _isolated_per_video() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_history(MOCK_OUTPUT, "video_a.mp4", tmp)
            save_history(MOCK_OUTPUT, "video_b.mp4", tmp)
            vlist_a = list_versions("video_a.mp4", tmp)
            vlist_b = list_versions("video_b.mp4", tmp)
            expect(len(vlist_a)).to_be(1)
            expect(len(vlist_b)).to_be(1)
    it("does not mix versions across videos", _isolated_per_video)


def _test_cli_rollback() -> None:
    def _default_is_none() -> None:
        opts = parse_cli_args(["video.mp4"])
        expect(opts["rollback_version"]).to_be(None)
    it("default is None", _default_is_none)

    def _parses_integer() -> None:
        opts = parse_cli_args(["video.mp4", "--rollback", "3"])
        expect(opts["rollback_version"]).to_be(3)
    it("parses --rollback 3 as int 3", _parses_integer)

    def _video_path_still_set() -> None:
        opts = parse_cli_args(["video.mp4", "--rollback", "2"])
        expect(opts["video_path"]).to_equal("video.mp4")
        expect(opts["rollback_version"]).to_be(2)
    it("keeps video path and rollback version", _video_path_still_set)

    def _ignores_non_numeric() -> None:
        opts = parse_cli_args(["video.mp4", "--rollback", "abc"])
        expect(opts["rollback_version"]).to_be(None)
    it("ignores non-numeric rollback value", _ignores_non_numeric)


def _test_cli_list_versions() -> None:
    def _default_is_none() -> None:
        opts = parse_cli_args(["video.mp4"])
        expect(opts["list_versions"]).to_be(None)
    it("default is None", _default_is_none)

    def _parses_flag() -> None:
        opts = parse_cli_args(["video.mp4", "--list-versions"])
        expect(opts["list_versions"]).to_be(True)
    it("parses --list-versions as True", _parses_flag)

    def _video_path_still_set() -> None:
        opts = parse_cli_args(["/path/to/video.mp4", "--list-versions"])
        expect(opts["video_path"]).to_equal("/path/to/video.mp4")
        expect(opts["list_versions"]).to_be(True)
    it("keeps video path alongside --list-versions", _video_path_still_set)
