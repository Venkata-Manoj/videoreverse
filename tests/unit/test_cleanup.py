from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.pipeline import _cleanup_temp_dir
from tests.unit.test_framework import describe, expect, it


def run_tests():
    describe("_cleanup_temp_dir", _test_all)


def _make_results(temp_dir: str | None) -> dict:
    if temp_dir is None:
        return {"steps": {}}
    return {"steps": {"ingest": {"output_dir": temp_dir}}}


def _test_all() -> None:
    it("removes temp directory when it exists", lambda: _run_remove_test())
    it("does not raise when output_dir key is missing", lambda: _run_missing_key_test())
    it("does not raise when output_dir is None", lambda: _run_none_test())
    it("does not raise when dir already removed", lambda: _run_already_removed_test())
    it("does not remove non-directory paths", lambda: _run_non_dir_test())
    it("removes directory with nested files", lambda: _run_nested_files_test())


def _run_remove_test() -> None:
    tmp = tempfile.mkdtemp(prefix="vidrev-test-")
    assert os.path.isdir(tmp)
    _cleanup_temp_dir(_make_results(tmp))
    expect(os.path.exists(tmp)).to_be(False)


def _run_missing_key_test() -> None:
    _cleanup_temp_dir({"steps": {}})


def _run_none_test() -> None:
    _cleanup_temp_dir({"steps": {"ingest": {"output_dir": None}}})


def _run_already_removed_test() -> None:
    tmp = tempfile.mkdtemp(prefix="vidrev-test-")
    os.rmdir(tmp)
    _cleanup_temp_dir(_make_results(tmp))
    expect(os.path.exists(tmp)).to_be(False)


def _run_non_dir_test() -> None:
    with tempfile.NamedTemporaryFile(prefix="vidrev-test-", suffix=".tmp", delete=False) as f:
        filepath = f.name
    try:
        _cleanup_temp_dir(_make_results(filepath))
        expect(os.path.exists(filepath)).to_be(True)
    finally:
        if os.path.exists(filepath):
            os.unlink(filepath)


def _run_nested_files_test() -> None:
    tmp = tempfile.mkdtemp(prefix="vidrev-test-")
    Path(tmp, "subdir").mkdir()
    Path(tmp, "subdir", "frame_0001.jpg").touch()
    Path(tmp, "subdir", "frame_0002.jpg").touch()
    Path(tmp, "audio.wav").touch()
    _cleanup_temp_dir(_make_results(tmp))
    expect(os.path.exists(tmp)).to_be(False)
