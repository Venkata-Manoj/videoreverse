from __future__ import annotations

import os
from pathlib import Path

import sys
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.path_resolver import normalize_for_env
from tests.unit.test_framework import describe, it, expect


def run_tests():
    describe("normalize_for_env", _test_windows_path)
    describe("normalize_for_env", _test_unix_path)
    describe("normalize_for_env", _test_url_passthrough)
    describe("normalize_for_env", _test_non_string)
    describe("normalize_for_env", _test_unc_path)
    describe("normalize_for_env", _test_already_wsl_path)
    describe("normalize_for_env", _test_wsl_mode_win)
    describe("normalize_for_env", _test_backslash_windows_path)
    describe("normalize_for_env", _test_edge_empty_string)
    describe("normalize_for_env", _test_edge_numeric_string)
    describe("normalize_for_env", _test_null_byte)
    describe("normalize_for_env", _test_relative_path)


def _test_windows_path() -> None:
    it("converts Windows drive path to WSL /mnt/ path", lambda: (
        expect(normalize_for_env("E:\\vidrev\\test.mp4")).to_be("/mnt/e/vidrev/test.mp4")
    ))

    it("converts Windows forward-slash path", lambda: (
        expect(normalize_for_env("C:/Users/test/video.mp4")).to_be("/mnt/c/Users/test/video.mp4")
    ))

    it("converts lower-case drive letter", lambda: (
        expect(normalize_for_env("d:\\videos\\clip.mp4")).to_be("/mnt/d/videos/clip.mp4")
    ))


def _test_unix_path() -> None:
    it("passes through Unix absolute path", lambda: (
        expect(normalize_for_env("/home/user/video.mp4")).to_be(os.path.abspath("/home/user/video.mp4"))
    ))

    it("passes through already-normalized /mnt/ path", lambda: (
        expect(normalize_for_env("/mnt/e/video.mp4")).to_be("/mnt/e/video.mp4")
    ))

    it("passes through /mnt/ with capital drive letter", lambda: (
        expect(normalize_for_env("/mnt/E/video.mp4")).to_be("/mnt/e/video.mp4")
    ))


def _test_url_passthrough() -> None:
    it("passes through https URLs", lambda: (
        expect(normalize_for_env("https://example.com/video.mp4")).to_be("https://example.com/video.mp4")
    ))

    it("passes through http URLs", lambda: (
        expect(normalize_for_env("http://storage.example/vids/test.mp4")).to_be("http://storage.example/vids/test.mp4")
    ))

    it("passes through s3 URLs", lambda: (
        expect(normalize_for_env("s3://bucket/video.mp4")).to_be("s3://bucket/video.mp4")
    ))

    it("passes through ftp URLs", lambda: (
        expect(normalize_for_env("ftp://server/path/video.mp4")).to_be("ftp://server/path/video.mp4")
    ))


def _test_non_string() -> None:
    it("returns integer as-is", lambda: (
        expect(normalize_for_env(42)).to_be(42)
    ))

    it("returns dict as-is", lambda: (
        expect(normalize_for_env({"key": "val"})).to_be({"key": "val"})
    ))

    it("returns list as-is", lambda: (
        expect(normalize_for_env(["/path/a.mp4", "/path/b.mp4"])).to_be(["/path/a.mp4", "/path/b.mp4"])
    ))

    it("returns None as-is", lambda: (
        expect(normalize_for_env(None)).to_be(None)
    ))


def _test_unc_path() -> None:
    it("converts UNC path to /mnt/ path", lambda: (
        expect(normalize_for_env("\\\\server\\share\\video.mp4")).to_be("/mnt/server/share/video.mp4")
    ))

    it("converts UNC path with multiple components", lambda: (
        expect(normalize_for_env("\\\\NAS\\videos\\2024\\test.mp4")).to_be("/mnt/nas/videos/2024/test.mp4")
    ))


def _test_already_wsl_path() -> None:
    it("returns WSL /mnt/ path unchanged", lambda: (
        expect(normalize_for_env("/mnt/e/video.mp4")).to_be("/mnt/e/video.mp4")
    ))

    it("returns WSL /mnt/ with nested dirs unchanged", lambda: (
        expect(normalize_for_env("/mnt/d/projects/videos/test_clip.mp4")).to_be("/mnt/d/projects/videos/test_clip.mp4")
    ))


def _test_wsl_mode_win() -> None:
    it("returns os.path.abspath when wsl_mode='win'", lambda: (
        expect(normalize_for_env("E:\\vidrev\\test.mp4", wsl_mode="win")).to_be(os.path.abspath("E:\\vidrev\\test.mp4"))
    ))


def _test_backslash_windows_path() -> None:
    it("handles mixed backslash/forward-slash paths", lambda: (
        expect(normalize_for_env("E:/videos\\test.mp4")).to_be("/mnt/e/videos/test.mp4")
    ))


def _test_edge_empty_string() -> None:
    it("returns abspath for empty string", lambda: (
        expect(normalize_for_env("") == os.path.abspath("")).to_be(True)
    ))


def _test_edge_numeric_string() -> None:
    it("returns abspath for numeric string", lambda: (
        expect(isinstance(normalize_for_env("12345"), str)).to_be(True)
    ))


def _test_null_byte() -> None:
    it("handles path with null byte gracefully", lambda: (
        expect(isinstance(normalize_for_env("/path/with\0null"), str)).to_be(True)
    ))


def _test_relative_path() -> None:
    it("converts relative path to absolute", lambda: (
        expect(normalize_for_env("relative/path/video.mp4")).to_be(os.path.abspath("relative/path/video.mp4"))
    ))
