from __future__ import annotations

from tests.unit.test_framework import expect, it

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.cli import PROFILES, SUPPORTED_PROFILES, parse_cli_args


def _fast_profile_applies_settings() -> None:
    opts = parse_cli_args(["--profile", "fast", "test.mp4"])
    expect(opts["profile"]).to_be("fast")
    expect(opts["sample_mode"]).to_be("first-n")
    expect(opts["max_duration"]).to_be(15)
    expect(opts["gemini_model"]).to_be("gemini-2.5-flash")

it("fast profile applies settings", _fast_profile_applies_settings)


def _quality_profile_applies_settings() -> None:
    opts = parse_cli_args(["--profile", "quality", "test.mp4"])
    expect(opts["profile"]).to_be("quality")
    expect(opts["sample_mode"]).to_be("full")
    expect(opts["gemini_model"]).to_be("gemini-2.5-pro")

it("quality profile applies settings", _quality_profile_applies_settings)


def _cheap_profile_applies_settings() -> None:
    opts = parse_cli_args(["--profile", "cheap", "test.mp4"])
    expect(opts["profile"]).to_be("cheap")
    expect(opts["sample_mode"]).to_be("highlights")
    expect(opts["max_duration"]).to_be(10)
    expect(opts["no_cache"]).to_be(True)

it("cheap profile applies settings", _cheap_profile_applies_settings)


def _explicit_flag_overrides_profile() -> None:
    opts = parse_cli_args(["--profile", "fast", "--sample-mode", "full", "test.mp4"])
    expect(opts["sample_mode"]).to_be("full")  # explicit override
    expect(opts["max_duration"]).to_be(15)  # still from profile
    expect(opts["gemini_model"]).to_be("gemini-2.5-flash")  # still from profile

it("explicit flag overrides profile", _explicit_flag_overrides_profile)


def _multiple_explicit_overrides() -> None:
    opts = parse_cli_args(["--profile", "cheap", "--gemini-model", "gemini-2.5-pro", "--max-duration", "30", "test.mp4"])
    expect(opts["profile"]).to_be("cheap")
    expect(opts["sample_mode"]).to_be("highlights")  # from profile
    expect(opts["max_duration"]).to_be(30)  # explicit override
    expect(opts["gemini_model"]).to_be("gemini-2.5-pro")  # explicit override
    expect(opts["no_cache"]).to_be(True)  # from profile

it("multiple explicit overrides", _multiple_explicit_overrides)


def _unknown_profile_is_ignored() -> None:
    opts = parse_cli_args(["--profile", "nonexistent", "test.mp4"])
    expect(opts["profile"]).to_be(None)
    expect(opts["sample_mode"]).to_be("full")  # default

it("unknown profile is ignored", _unknown_profile_is_ignored)


def _no_profile_is_default() -> None:
    opts = parse_cli_args(["test.mp4"])
    expect(opts["profile"]).to_be(None)
    expect(opts["sample_mode"]).to_be("full")
    expect(opts["gemini_model"]).to_be("gemini-2.5-flash")
    expect(opts["max_duration"]).to_be(None)
    expect(opts["no_cache"]).to_be(False)

it("no profile gives default settings", _no_profile_is_default)


def _profile_from_web_backend() -> None:
    opts = parse_cli_args(["test.mp4", "--profile", "quality"])
    expect(opts["profile"]).to_be("quality")
    expect(opts["gemini_model"]).to_be("gemini-2.5-pro")

it("profile flag works with video path", _profile_from_web_backend)


def _profile_with_no_args_is_valid() -> None:
    opts = parse_cli_args(["--profile", "fast"])
    expect(opts["profile"]).to_be("fast")

it("profile with no video path is valid", _profile_with_no_args_is_valid)


def _profiles_have_required_keys() -> None:
    for name, cfg in PROFILES.items():
        expect("description" in cfg).to_be(True)
        expect("sample_mode" in cfg).to_be(True)

it("all profiles have required keys", _profiles_have_required_keys)


def _supported_profiles_list_matches() -> None:
    for name in SUPPORTED_PROFILES:
        expect(name in PROFILES).to_be(True)

it("SUPPORTED_PROFILES matches PROFILES dict", _supported_profiles_list_matches)


def _quality_profile_no_max_duration() -> None:
    opts = parse_cli_args(["--profile", "quality", "test.mp4"])
    expect(opts["max_duration"]).to_be(None)

it("quality profile does not set max_duration", _quality_profile_no_max_duration)
