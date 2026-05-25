from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from typing import Any
from unittest.mock import patch

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.interactive import (
    ALIASES,
    COMMANDS,
    OUTPUT_DIR,
    SESSION_STATE,
    cmd_compare,
    cmd_export,
    cmd_help,
    cmd_list,
    cmd_regenerate,
    cmd_save,
    cmd_show,
    cmd_status,
    start_interactive,
    _save_current_output,
)

from tests.unit.test_framework import describe, it, expect


def _make_session(**overrides: Any) -> dict[str, Any]:
    return {
        "blueprint": {
            "global_aesthetic": {
                "art_style": "cinematic",
                "color_grading": "warm",
                "lighting_setup": "natural",
            },
            "chronological_shots": [
                {
                    "shot_index": 0,
                    "duration_seconds": 3.0,
                    "camera_direction": "static",
                    "framing_type": "wide",
                    "action_and_motion": "character walking",
                    "environment_context": "forest",
                },
                {
                    "shot_index": 1,
                    "duration_seconds": 5.0,
                    "camera_direction": "pan right",
                    "framing_type": "medium",
                    "action_and_motion": "bird flying",
                    "environment_context": "sky",
                },
            ],
        },
        "prompts": {
            "runway_gen4_5": {
                "label": "Runway Gen-4.5",
                "shots": [{"prompt": "A cinematic shot of a forest."}, {"prompt": "A pan right shot of the sky."}],
            }
        },
        "video_metadata": {
            "filename": "test_video.mp4",
            "duration_seconds": 8.0,
            "width": 1920,
            "height": 1080,
        },
        "full_output": {
            "video_metadata": {
                "filename": "test_video.mp4",
                "duration_seconds": 8.0,
                "width": 1920,
                "height": 1080,
            },
            "blueprint": {
                "global_aesthetic": {
                    "art_style": "cinematic",
                    "color_grading": "warm",
                    "lighting_setup": "natural",
                },
                "chronological_shots": [
                    {
                        "shot_index": 0,
                        "duration_seconds": 3.0,
                        "camera_direction": "static",
                        "framing_type": "wide",
                        "action_and_motion": "character walking",
                        "environment_context": "forest",
                    },
                    {
                        "shot_index": 1,
                        "duration_seconds": 5.0,
                        "camera_direction": "pan right",
                        "framing_type": "medium",
                        "action_and_motion": "bird flying",
                        "environment_context": "sky",
                    },
                ],
            },
            "prompts": {
                "runway_gen4_5": {
                    "label": "Runway Gen-4.5",
                    "shots": [{"prompt": "A cinematic shot of a forest."}, {"prompt": "A pan right shot of the sky."}],
                }
            },
            "_meta": {"fallback_active": False},
        },
        **overrides,
    }


def _capture_output(func, *args, **kwargs) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    return buf.getvalue()


def run_tests() -> None:
    # ── Setup ──
    empty_session = _make_session()
    # Clear any global state
    SESSION_STATE.clear()
    globals()["OUTPUT_DIR"] = None  # type: ignore[name-defined]

    describe("cmd_help", _test_help)
    describe("cmd_status", _test_status)
    describe("cmd_show", _test_show)
    describe("cmd_regenerate", _test_regenerate)
    describe("cmd_compare", _test_compare)
    describe("cmd_export", _test_export)
    describe("cmd_save", _test_save)
    describe("cmd_list", _test_list)
    describe("ALIASES construction", _test_aliases)
    describe("_save_current_output", _test_save_output)
    describe("start_interactive loop", _test_start_interactive)


def _test_help() -> None:
    def _prints_help_text() -> None:
        out = _capture_output(cmd_help)
        expect("Available commands:" in out).to_be(True)
        expect("help, h" in out).to_be(True)
        expect("status, st" in out).to_be(True)
        expect("regenerate" in out).to_be(True)
        expect("edit" in out).to_be(True)
        expect("compare" in out).to_be(True)
        expect("export" in out).to_be(True)
        expect("list models" in out).to_be(True)
        expect("quit" in out).to_be(True)

    it("prints all commands", _prints_help_text)

    def _accepts_extra_args() -> None:
        out = _capture_output(cmd_help, ["extra", "args"])
        expect("Available commands:" in out).to_be(True)

    it("handles extra args gracefully", _accepts_extra_args)


def _test_status() -> None:
    def _shows_full_session_info() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        SESSION_STATE.update(session)
        out = _capture_output(cmd_status)
        expect("test_video.mp4" in out).to_be(True)
        expect("8.0s" in out).to_be(True)
        expect("1920x1080" in out).to_be(True)
        expect("2 shots" in out).to_be(True)
        expect("1" in out).to_be(True)

    it("shows full session info", _shows_full_session_info)

    def _handles_empty_session() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"blueprint": {}, "prompts": {}, "video_metadata": {}, "full_output": {}})
        out = _capture_output(cmd_status)
        expect("N/A" in out).to_be(True)
        expect("?" in out).to_be(True)

    it("handles empty session gracefully", _handles_empty_session)

    def _handles_missing_keys() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"blueprint": {"chronological_shots": None}, "prompts": None})
        out = _capture_output(cmd_status)
        # Should not crash
        expect(len(out) > 0).to_be(True)

    it("handles None values without crashing", _handles_missing_keys)

    def _shows_fallback_when_active() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        session["full_output"] = {"_meta": {"fallback_active": True}}
        SESSION_STATE.update(session)
        out = _capture_output(cmd_status)
        expect("Yes" in out).to_be(True)

    it("shows fallback when active", _shows_fallback_when_active)

    def _shows_no_fallback_when_inactive() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        session["full_output"] = {"_meta": {"fallback_active": False}}
        SESSION_STATE.update(session)
        out = _capture_output(cmd_status)
        expect("No" in out).to_be(True)

    it("shows no fallback when inactive", _shows_no_fallback_when_inactive)

    def _handles_missing_full_output() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"blueprint": {}, "prompts": {}, "video_metadata": {}})
        out = _capture_output(cmd_status)
        expect("Fallback:" in out).to_be(True)
        expect("No" in out).to_be(True)

    it("handles missing full_output gracefully", _handles_missing_full_output)

    def _handles_non_dict_model_in_status() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({
            "blueprint": {"chronological_shots": [{}]},
            "prompts": {"m1": "not_a_dict", "m2": {"label": "Good Model", "shots": [{}]}},
            "video_metadata": {"filename": "t.mp4", "duration_seconds": 5, "width": 100, "height": 100},
            "full_output": {"_meta": {}},
        })
        out = _capture_output(cmd_status)
        expect("Good Model" in out).to_be(True)
        expect("m1" in out).to_be(False)

    it("skips non-dict model entries in status", _handles_non_dict_model_in_status)


def _test_show() -> None:
    def _shows_blueprint_and_prompts() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        SESSION_STATE.update(session)
        out = _capture_output(cmd_show)
        expect("cinematic" in out).to_be(True)
        expect("warm" in out).to_be(True)
        expect("natural" in out).to_be(True)
        expect("2" in out).to_be(True)
        expect("character walking" in out).to_be(True)
        expect("bird flying" in out).to_be(True)
        expect("Runway Gen-4.5" in out).to_be(True)

    it("shows blueprint aesthetic, shots, and model prompts", _shows_blueprint_and_prompts)

    def _handles_empty_output() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"full_output": {}})
        out = _capture_output(cmd_show)
        expect("No output available" in out).to_be(True)

    it("handles empty output gracefully", _handles_empty_output)

    def _handles_no_output() -> None:
        SESSION_STATE.clear()
        out = _capture_output(cmd_show)
        expect("No output available" in out).to_be(True)

    it("handles missing output gracefully", _handles_no_output)

    def _handles_output_with_missing_blueprint() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"full_output": {"prompts": {}, "_meta": {}}})
        out = _capture_output(cmd_show)
        expect("Global Aesthetic" in out).to_be(True)
        expect("Models: 0" in out).to_be(True)

    it("handles output with missing blueprint gracefully", _handles_output_with_missing_blueprint)

    def _handles_none_prompts_in_output() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"full_output": {"blueprint": {"global_aesthetic": {}}, "prompts": None}})
        out = _capture_output(cmd_show)
        expect("Models: 0" in out).to_be(True)

    it("handles None prompts in output", _handles_none_prompts_in_output)

    def _handles_non_dict_models_in_prompts() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"full_output": {"blueprint": {"global_aesthetic": {}}, "prompts": {"bad_model": "not_a_dict"}}})
        out = _capture_output(cmd_show)
        expect("Models: 1" in out).to_be(True)
        # Should not crash on .get() for non-dict

    it("handles non-dict model entries gracefully", _handles_non_dict_models_in_prompts)


def _test_regenerate() -> None:
    def _handles_regenerate_with_empty_prompts() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        session["prompts"] = {}
        session["full_output"]["prompts"] = {}
        SESSION_STATE.update(session)
        out = _capture_output(cmd_regenerate, ["all"])
        expect("Recompiling" in out).to_be(True)

    it("handles regenerate with empty prompts dict", _handles_regenerate_with_empty_prompts)

    def _handles_regenerate_with_no_full_output() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({
            "blueprint": {"global_aesthetic": {}, "chronological_shots": [{}]},
            "video_metadata": {"filename": "t.mp4", "duration_seconds": 5},
        })
        out = _capture_output(cmd_regenerate, ["all"])
        expect("Recompiling" in out).to_be(True)

    it("handles regenerate when full_output not yet set", _handles_regenerate_with_no_full_output)
    def _requires_model_arg() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        SESSION_STATE.update(session)
        out = _capture_output(cmd_regenerate, [])
        expect("Usage:" in out).to_be(True)

    it("shows usage when no args given", _requires_model_arg)

    def _requires_blueprint() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"blueprint": None, "prompts": {}, "video_metadata": {}})
        out = _capture_output(cmd_regenerate, ["runway_gen4_5"])
        expect("No blueprint available" in out).to_be(True)

    it("reports missing blueprint gracefully", _requires_blueprint)

    def _handles_invalid_model() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        SESSION_STATE.update(session)
        out = _capture_output(cmd_regenerate, ["nonexistent_model"])
        expect("Recompiled 0 model" in out).to_be(True)

    it("gracefully compiles 0 models for unknown model name", _handles_invalid_model)

    def _recompiles_all_when_target_is_all() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        SESSION_STATE.update(session)
        # "all" should not crash - filter_models will be None
        out = _capture_output(cmd_regenerate, ["all"])
        # Should attempt compilation with all models
        expect("Recompiling" in out).to_be(True)

    it('accepts "all" as target', _recompiles_all_when_target_is_all)


def _test_compare() -> None:
    def _requires_two_file_args() -> None:
        out = _capture_output(cmd_compare, [])
        expect("Usage:" in out).to_be(True)

    it("shows usage when no args given", _requires_two_file_args)

    def _shows_usage_with_one_arg() -> None:
        out = _capture_output(cmd_compare, ["file1.json"])
        expect("Usage:" in out).to_be(True)

    it("shows usage with only one arg", _shows_usage_with_one_arg)

    def _handles_missing_file() -> None:
        out = _capture_output(cmd_compare, ["/tmp/nonexistent_1.json", "/tmp/nonexistent_2.json"])
        expect("not found" in out).to_be(True)

    it("reports missing files gracefully", _handles_missing_file)

    def _handles_valid_comparison() -> None:
        data1 = {"prompts": {"m1": {"label": "M1", "shots": [{"prompt": "hello world"}]}}}
        data2 = {"prompts": {"m1": {"label": "M1", "shots": [{"prompt": "hello there"}]}}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f1:
            json.dump(data1, f1)
            p1 = f1.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f2:
            json.dump(data2, f2)
            p2 = f2.name
        try:
            out = _capture_output(cmd_compare, [p1, p2])
            expect("Comparison Report" in out).to_be(True)
            expect("m1" in out).to_be(True)
            expect("modified" in out).to_be(True)
            expect("55%" in out).to_be(True)
        finally:
            os.unlink(p1)
            os.unlink(p2)

    it("compares two valid JSON files", _handles_valid_comparison)

    def _handles_comparing_same_file() -> None:
        data = {"prompts": {"m1": {"label": "M1", "shots": [{"prompt": "same"}]}}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            p = f.name
        try:
            out = _capture_output(cmd_compare, [p, p])
            expect("unchanged" in out).to_be(True)
        finally:
            os.unlink(p)

    it("handles comparing the same file", _handles_comparing_same_file)

    def _handles_invalid_json() -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f1:
            f1.write("not valid json")
            p1 = f1.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f2:
            f2.write("also not json")
            p2 = f2.name
        try:
            out = _capture_output(cmd_compare, [p1, p2])
            expect("failed" in out.lower()).to_be(True)
        finally:
            os.unlink(p1)
            os.unlink(p2)

    it("handles invalid JSON in files gracefully", _handles_invalid_json)


def _test_export() -> None:
    def _requires_format_arg() -> None:
        out = _capture_output(cmd_export, [])
        expect("Usage:" in out).to_be(True)

    it("shows usage when no format given", _requires_format_arg)

    def _rejects_invalid_format() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        SESSION_STATE.update(session)
        out = _capture_output(cmd_export, ["pdf"])
        expect("Invalid format" in out).to_be(True)

    it("rejects invalid format", _rejects_invalid_format)

    def _requires_output_in_session() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"full_output": None})
        out = _capture_output(cmd_export, ["json"])
        expect("No output" in out).to_be(True)

    it("reports when no output in session", _requires_output_in_session)


def _test_save() -> None:
    def _requires_output() -> None:
        SESSION_STATE.clear()
        SESSION_STATE.update({"full_output": None})
        out = _capture_output(cmd_save)
        expect("No output" in out).to_be(True)

    it("reports when no output to save", _requires_output)

    def _saves_output_to_disk() -> None:
        SESSION_STATE.clear()
        session = _make_session()
        SESSION_STATE.update(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            import utils.interactive
            old_out = utils.interactive.OUTPUT_DIR
            utils.interactive.OUTPUT_DIR = tmpdir
            try:
                out = _capture_output(cmd_save)
                expect("Saved:" in out).to_be(True)
                files = os.listdir(tmpdir)
                json_files = [f for f in files if f.endswith(".json")]
                txt_files = [f for f in files if f.endswith(".txt")]
                expect(len(json_files)).to_be(1)
                expect(len(txt_files)).to_be(1)
            finally:
                utils.interactive.OUTPUT_DIR = old_out

    it("saves json and txt files to disk", _saves_output_to_disk)


def _test_list() -> None:
    def _shows_usage_with_no_subcommand() -> None:
        out = _capture_output(cmd_list, [])
        expect("Usage:" in out).to_be(True)

    it("shows usage with no subcommand", _shows_usage_with_no_subcommand)

    def _shows_models() -> None:
        out = _capture_output(cmd_list, ["models"])
        expect("Available models" in out).to_be(True)
        expect("runway_gen4_5" in out).to_be(True)
        expect("google_veo3_1" in out).to_be(True)

    it("lists available models", _shows_models)

    def _handles_missing_output_dir() -> None:
        import utils.interactive
        old_out = utils.interactive.OUTPUT_DIR
        utils.interactive.OUTPUT_DIR = "/tmp/vidrev_nonexistent_test_dir_xyz"
        try:
            out = _capture_output(cmd_list, ["files"])
            expect("not found" in out).to_be(True)
        finally:
            utils.interactive.OUTPUT_DIR = old_out

    it("reports missing output dir gracefully", _handles_missing_output_dir)

    def _shows_empty_output_dir() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            import utils.interactive
            old_out = utils.interactive.OUTPUT_DIR
            utils.interactive.OUTPUT_DIR = tmpdir
            try:
                out = _capture_output(cmd_list, ["files"])
                expect("No output files" in out).to_be(True)
            finally:
                utils.interactive.OUTPUT_DIR = old_out

    it("reports empty output directory", _shows_empty_output_dir)

    def _shows_files_in_directory() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "test_output.json"), "w").write("{}")
            open(os.path.join(tmpdir, "test_output.txt"), "w").write("test")
            open(os.path.join(tmpdir, "readme.md"), "w").write("# readme")
            import utils.interactive
            old_out = utils.interactive.OUTPUT_DIR
            utils.interactive.OUTPUT_DIR = tmpdir
            try:
                out = _capture_output(cmd_list, ["files"])
                expect("test_output.json" in out).to_be(True)
                expect("test_output.txt" in out).to_be(True)
                expect("readme.md" in out).to_be(False)
            finally:
                utils.interactive.OUTPUT_DIR = old_out

    it("lists only json and txt files", _shows_files_in_directory)


def _test_aliases() -> None:
    def _maps_all_aliases_correctly() -> None:
        expect(ALIASES["h"]).to_be("help")
        expect(ALIASES["st"]).to_be("status")
        expect(ALIASES["regen"]).to_be("regenerate")
        expect(ALIASES["e"]).to_be("edit")
        expect(ALIASES["diff"]).to_be("compare")
        expect(ALIASES["ex"]).to_be("export")
        expect(ALIASES["ls"]).to_be("list")
        expect(ALIASES["exit"]).to_be("quit")

    it("maps all aliases correctly", _maps_all_aliases_correctly)

    def _canonical_commands_are_not_in_aliases() -> None:
        expect("q" in ALIASES).to_be(False)
        expect("quit" in ALIASES).to_be(True)

    it("canonical 'q' not in ALIASES (resolved via COMMANDS)", _canonical_commands_are_not_in_aliases)

    def _all_commands_accessible_via_resolution() -> None:
        test_inputs = ["help", "h", "show", "regen", "edit", "e", "compare", "diff", "export", "ex", "save", "list", "ls", "quit", "exit", "q"]
        for cmd in test_inputs:
            resolved = ALIASES.get(cmd, cmd)
            expect(resolved in COMMANDS).to_be(True)

    it("all command names and aliases resolve to a registered command", _all_commands_accessible_via_resolution)

    def _does_not_create_alias_for_empty_alias() -> None:
        expect("show" in ALIASES).to_be(False)
        expect("save" in ALIASES).to_be(False)

    it("does not create alias for commands with empty alias", _does_not_create_alias_for_empty_alias)

    # Not tested: "all aliases map back to their canonical"
    # because shared aliases (e.g., "quit" → "exit" and "quit" → "q")
    # cause overwrites. The resolution test above covers correctness.


def _test_save_output() -> None:
    def _saves_json_and_txt_to_dir() -> None:
        session = _make_session()
        output = session["full_output"]
        with tempfile.TemporaryDirectory() as tmpdir:
            import utils.interactive
            old_out = utils.interactive.OUTPUT_DIR
            utils.interactive.OUTPUT_DIR = tmpdir
            try:
                path = _save_current_output(output)
                expect(os.path.exists(path)).to_be(True)
                with open(path) as f:
                    data = json.load(f)
                expect("video_metadata" in data).to_be(True)
                expect("blueprint" in data).to_be(True)
                expect("prompts" in data).to_be(True)
                txt_path = path.replace(".json", ".txt")
                expect(os.path.exists(txt_path)).to_be(True)
            finally:
                utils.interactive.OUTPUT_DIR = old_out

    it("saves valid json and txt files", _saves_json_and_txt_to_dir)

    def _handles_missing_filename_in_metadata() -> None:
        output = {"video_metadata": {}, "blueprint": {}, "prompts": {}}
        with tempfile.TemporaryDirectory() as tmpdir:
            import utils.interactive
            old_out = utils.interactive.OUTPUT_DIR
            utils.interactive.OUTPUT_DIR = tmpdir
            try:
                path = _save_current_output(output)
                expect(os.path.exists(path)).to_be(True)
            finally:
                utils.interactive.OUTPUT_DIR = old_out

    it("uses fallback filename when metadata missing", _handles_missing_filename_in_metadata)


def _test_start_interactive() -> None:
    def _handles_help_command() -> None:
        session = _make_session()
        buf = io.StringIO()
        with redirect_stdout(buf), patch("builtins.input", side_effect=["help", "quit"]):
            start_interactive(session)
        out = buf.getvalue()
        expect("Interactive Mode" in out).to_be(True)
        expect("Available commands" in out).to_be(True)
        expect("Goodbye!" in out).to_be(True)

    it("handles help then quit", _handles_help_command)

    def _handles_unknown_command() -> None:
        session = _make_session()
        buf = io.StringIO()
        with redirect_stdout(buf), patch("builtins.input", side_effect=["foobar", "quit"]):
            start_interactive(session)
        out = buf.getvalue()
        expect("Unknown command" in out).to_be(True)

    it("reports unknown commands", _handles_unknown_command)

    def _handles_empty_input() -> None:
        session = _make_session()
        buf = io.StringIO()
        with redirect_stdout(buf), patch("builtins.input", side_effect=["", "  ", "quit"]):
            start_interactive(session)
        out = buf.getvalue()
        expect("Goodbye!" in out).to_be(True)

    it("handles empty and whitespace input", _handles_empty_input)

    def _handles_ctrl_c() -> None:
        session = _make_session()
        buf = io.StringIO()
        with redirect_stdout(buf), patch("builtins.input", side_effect=KeyboardInterrupt()):
            start_interactive(session)
        out = buf.getvalue()
        expect("Goodbye!" in out).to_be(True)

    it("handles KeyboardInterrupt (Ctrl+C)", _handles_ctrl_c)

    def _handles_eof() -> None:
        session = _make_session()
        buf = io.StringIO()
        with redirect_stdout(buf), patch("builtins.input", side_effect=EOFError()):
            start_interactive(session)
        out = buf.getvalue()
        expect("Goodbye!" in out).to_be(True)

    it("handles EOFError (Ctrl+D)", _handles_eof)

    def _handles_status_command() -> None:
        session = _make_session()
        buf = io.StringIO()
        with redirect_stdout(buf), patch("builtins.input", side_effect=["status", "quit"]):
            start_interactive(session)
        out = buf.getvalue()
        expect("test_video.mp4" in out).to_be(True)
        expect("2 shots" in out).to_be(True)

    it("runs status command within loop", _handles_status_command)
