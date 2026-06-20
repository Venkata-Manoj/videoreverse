from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.unit.test_framework import describe, expect, it
from utils.cli import parse_cli_args


def run_tests():
    describe("parse_cli_args --quiet", _test_quiet_sets_log_level)
    describe("parse_cli_args -q", _test_q_sets_log_level)
    describe("parse_cli_args --log-level quiet", _test_log_level_quiet)
    describe("parse_cli_args quiet + verbose", _test_verbose_overrides_quiet)
    describe("parse_cli_args quiet + dry_run", _test_quiet_with_dry_run)


def _test_quiet_sets_log_level() -> None:
    def _quiet() -> None:
        opts = parse_cli_args(["--quiet", "test.mp4"])
        expect(opts["quiet"]).to_be(True)
        expect(opts["log_level"]).to_be("quiet")
    it("sets log_level to quiet", _quiet)

    def _no_side_effects() -> None:
        opts = parse_cli_args(["--quiet", "test.mp4"])
        expect(opts["dry_run"]).to_be(False)
        expect(opts["verbose"]).to_be(False)
        expect(opts["video_path"]).to_be("test.mp4")
    it("does not set unrelated flags", _no_side_effects)


def _test_q_sets_log_level() -> None:
    def _f() -> None:
        opts = parse_cli_args(["-q", "test.mp4"])
        expect(opts["quiet"]).to_be(True)
        expect(opts["log_level"]).to_be("quiet")
    it("sets log_level to quiet with -q", _f)


def _test_log_level_quiet() -> None:
    def _f() -> None:
        opts = parse_cli_args(["--log-level", "quiet", "test.mp4"])
        expect(opts["log_level"]).to_be("quiet")
        expect(opts["quiet"]).to_be(False)
    it("accepts --log-level quiet without setting quiet flag", _f)

    def _invalid() -> None:
        try:
            parse_cli_args(["--log-level", "invalid", "test.mp4"])
            expect(True).to_be(False)
        except ValueError as e:
            expect("Invalid log level" in str(e)).to_be(True)
    it("rejects invalid log level value", _invalid)


def _test_verbose_overrides_quiet() -> None:
    def _f() -> None:
        opts = parse_cli_args(["--quiet", "--verbose", "test.mp4"])
        expect(opts["log_level"]).to_be("debug")
    it("last flag wins for log_level", _f)


def _test_quiet_with_dry_run() -> None:
    def _f() -> None:
        opts = parse_cli_args(["--quiet", "--dry-run", "test.mp4"])
        expect(opts["quiet"]).to_be(True)
        expect(opts["dry_run"]).to_be(True)
        expect(opts["log_level"]).to_be("quiet")
    it("dry_run flag works alongside quiet", _f)
