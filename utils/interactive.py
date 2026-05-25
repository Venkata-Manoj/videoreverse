from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from typing import Any

from src.compile import compile_prompts, _load_templates
from src.export import format_text
from utils.compare import compare_prompts, print_comparison, save_comparison
from utils.error_codes import VRError, VRErrorCode
from utils.logger import info

SESSION_STATE: dict[str, Any] = {}
OUTPUT_DIR: str | None = None


def _save_current_output(output: dict[str, Any]) -> str:
    global OUTPUT_DIR
    out_dir = OUTPUT_DIR or "output_blueprints"
    os.makedirs(out_dir, exist_ok=True)
    filename = output.get("video_metadata", {}).get("filename", "output")
    base = os.path.splitext(filename)[0]
    ts = datetime.now(UTC).isoformat().replace(":", "-").replace(".", "-")
    path = os.path.join(out_dir, f"{base}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"  Saved: {path}", flush=True)
    txt_path = os.path.join(out_dir, f"{base}_{ts}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(format_text(output))
    print(f"  Saved: {txt_path}", flush=True)
    return path


def cmd_help(*_) -> None:
    print("""
  Available commands:
    help, h                  Show this help
    status, st               Show session info
    show                     Show current output summary

    regenerate <model>,      Re-compile prompts for a model (or all)
      regen <model>

    edit <model>             Edit template for a model ($EDITOR or inline)

    compare <file1> <file2>,  Compare two output JSON files
      diff <file1> <file2>

    export <format>          Re-export: json, txt, both
    save                     Save current output to disk

    list models,             List available models
      ls models
    list files               List saved output files

    quit, exit, q            Exit interactive mode
""")


def cmd_status(*_) -> None:
    meta = SESSION_STATE.get("video_metadata", {})
    bp = SESSION_STATE.get("blueprint", {})
    prompts = SESSION_STATE.get("prompts", {})
    output = SESSION_STATE.get("full_output", {})

    print(f"\n  Video:         {meta.get('filename', 'N/A')}", flush=True)
    print(f"  Duration:      {meta.get('duration_seconds', '?')}s", flush=True)
    print(f"  Resolution:    {meta.get('width', '?')}x{meta.get('height', '?')}", flush=True)
    print(f"  Shots:         {len(bp.get('chronological_shots', []))}", flush=True)
    print(f"  Models:        {len(prompts)}", flush=True)
    print(f"  Fallback:      {'Yes' if output.get('_meta', {}).get('fallback_active') else 'No'}", flush=True)

    if prompts:
        print(f"\n  Compiled models:", flush=True)
        for key, model in prompts.items():
            shots = len(model.get("shots", []))
            print(f"    • {model.get('label', key)} ({shots} shots)", flush=True)
    print(flush=True)


def cmd_show(*_) -> None:
    output = SESSION_STATE.get("full_output")
    if not output:
        print("  No output available. Run the pipeline first.", flush=True)
        return
    bp = output.get("blueprint", {})
    aesthetic = bp.get("global_aesthetic", {})
    shots = bp.get("chronological_shots", [])
    prompts = output.get("prompts", {})

    print(f"\n  Global Aesthetic:", flush=True)
    print(f"    Style:   {aesthetic.get('art_style', '-')}", flush=True)
    print(f"    Lighting: {aesthetic.get('lighting_setup', '-')}", flush=True)
    print(f"    Color:    {aesthetic.get('color_grading', '-')}", flush=True)
    print(f"\n  Shots: {len(shots)}", flush=True)
    for i, shot in enumerate(shots):
        print(f"    {i + 1}. ({shot.get('duration_seconds', '?'):>4}s) {shot.get('camera_direction', '-'):>12} — {shot.get('action_and_motion', '-')[:60]}", flush=True)
    print(f"\n  Models: {len(prompts)}", flush=True)
    for key, model in prompts.items():
        print(f"    • {model.get('label', key)}", flush=True)
    print(flush=True)


def cmd_regenerate(args: list[str]) -> None:
    if not args:
        print("  Usage: regenerate <model>  (or 'regen all' for all models)", flush=True)
        return

    target = args[0].lower()
    blueprint = SESSION_STATE.get("blueprint")
    meta = SESSION_STATE.get("video_metadata")
    if not blueprint:
        print("  No blueprint available. Run the pipeline first.", flush=True)
        return

    filter_models = None if target == "all" else [args[0]]

    try:
        print(f"  Recompiling prompts...", flush=True)
        prompts = compile_prompts(blueprint, meta, filter_models=filter_models)

        output = SESSION_STATE.get("full_output", {})
        output["prompts"] = prompts
        SESSION_STATE["prompts"] = prompts
        SESSION_STATE["full_output"] = output

        print(f"  ✓ Recompiled {len(prompts)} model(s)", flush=True)
    except Exception as err:
        print(f"  ✗ Failed: {err}", flush=True)


def cmd_edit(args: list[str]) -> None:
    if not args:
        print("  Usage: edit <model_id>", flush=True)
        print("  Models: " + ", ".join(SESSION_STATE.get("prompts", {}).keys()), flush=True)
        return

    model_id = args[0]
    templates = _load_templates()
    if model_id not in templates:
        print(f"  ✗ Model '{model_id}' not found.", flush=True)
        print(f"  Available: {', '.join(templates.keys())}", flush=True)
        return

    template = templates[model_id]["template"]
    editor = os.environ.get("EDITOR", "vi")

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(f"# Edit template for: {model_id}\n")
            f.write(f"# Lines starting with # are comments — they will be ignored.\n")
            f.write(f"# Leave the file unchanged to abort.\n\n")
            f.write(template)
            f.write("\n")
            tmp_path = f.name

        os.system(f"{editor} {tmp_path}")

        with open(tmp_path, encoding="utf-8") as f:
            lines = [l for l in f.read().split("\n") if not l.strip().startswith("#")]
        new_template = "\n".join(lines).strip()

        if new_template == template:
            print("  Template unchanged.", flush=True)
        elif not new_template:
            print("  Template cannot be empty. Aborted.", flush=True)
        else:
            templates[model_id]["template"] = new_template
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "prompt_templates.json",
            )
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(templates, f, indent=2)

            print(f"  ✓ Template for '{model_id}' updated.", flush=True)

            blueprint = SESSION_STATE.get("blueprint")
            meta = SESSION_STATE.get("video_metadata")
            if blueprint and meta and new_template != template:
                print(f"  Auto-regenerating prompts for '{model_id}'...", flush=True)
                prompts = compile_prompts(blueprint, meta, filter_models=[model_id])
                output = SESSION_STATE.get("full_output", {})
                merged = {**output.get("prompts", {}), **prompts}
                output["prompts"] = merged
                SESSION_STATE["prompts"] = merged
                SESSION_STATE["full_output"] = output
                print(f"  ✓ Regenerated prompts for '{model_id}'", flush=True)

        os.unlink(tmp_path)

    except Exception as err:
        print(f"  ✗ Edit failed: {err}", flush=True)


def cmd_compare(args: list[str]) -> None:
    if len(args) < 2:
        print("  Usage: compare <file1.json> <file2.json>", flush=True)
        return

    file1, file2 = args[0], args[1]
    if not os.path.exists(file1):
        print(f"  ✗ File not found: {file1}", flush=True)
        return
    if not os.path.exists(file2):
        print(f"  ✗ File not found: {file2}", flush=True)
        return

    try:
        with open(file1, encoding="utf-8") as f:
            data1 = json.load(f)
        with open(file2, encoding="utf-8") as f:
            data2 = json.load(f)

        result = compare_prompts(data1, data2)
        print_comparison(result)
    except Exception as err:
        print(f"  ✗ Comparison failed: {err}", flush=True)


def cmd_export(args: list[str]) -> None:
    if not args:
        print("  Usage: export <format>  (json, txt, both)", flush=True)
        return

    fmt = args[0].lower()
    if fmt not in ("json", "txt", "both"):
        print(f"  ✗ Invalid format: {fmt}. Use: json, txt, both", flush=True)
        return

    output = SESSION_STATE.get("full_output")
    if not output:
        print("  No output to export.", flush=True)
        return

    path = _save_current_output(output)
    print(f"  ✓ Exported as {fmt}: {path}", flush=True)


def cmd_save(*_) -> None:
    output = SESSION_STATE.get("full_output")
    if not output:
        print("  No output to save.", flush=True)
        return
    _save_current_output(output)


def cmd_list(args: list[str]) -> None:
    sub = args[0] if args else ""
    if sub == "models":
        templates = _load_templates()
        print(f"\n  Available models ({len(templates)}):", flush=True)
        for key, config in templates.items():
            label = config.get("label", key)
            max_dur = config.get("max_duration", "?")
            neg = "✓" if config.get("supports_negative") else "✗"
            print(f"    • {key:>25}  {label:<20}  max: {max_dur}s  neg: {neg}", flush=True)
        print(flush=True)
    elif sub == "files":
        out_dir = OUTPUT_DIR or "output_blueprints"
        if not os.path.exists(out_dir):
            print(f"  Output directory '{out_dir}' not found.", flush=True)
            return
        files = sorted(os.listdir(out_dir))
        jsons = [f for f in files if f.endswith(".json")]
        txts = [f for f in files if f.endswith(".txt")]
        if not jsons and not txts:
            print(f"  No output files found in '{out_dir}'.", flush=True)
            return
        print(f"\n  Output files in '{out_dir}':", flush=True)
        for f in jsons:
            size = os.path.getsize(os.path.join(out_dir, f))
            print(f"    📄 {f:<50} {size / 1024:.1f} KB", flush=True)
        for f in txts:
            size = os.path.getsize(os.path.join(out_dir, f))
            print(f"    📝 {f:<50} {size / 1024:.1f} KB", flush=True)
        print(flush=True)
    else:
        print("  Usage: list models | list files", flush=True)


COMMANDS: dict[str, tuple[str, Any, str]] = {
    "help": ("h", cmd_help, "Show this help"),
    "status": ("st", cmd_status, "Show session info"),
    "show": ("", cmd_show, "Show current output"),
    "regenerate": ("regen", cmd_regenerate, "Re-compile prompts for a model"),
    "regen": ("regenerate", cmd_regenerate, ""),
    "edit": ("e", cmd_edit, "Edit template for a model"),
    "e": ("edit", cmd_edit, ""),
    "compare": ("diff", cmd_compare, "Compare two output JSON files"),
    "diff": ("compare", cmd_compare, ""),
    "export": ("ex", cmd_export, "Re-export output in a format"),
    "ex": ("export", cmd_export, ""),
    "save": ("", cmd_save, "Save current output to disk"),
    "list": ("ls", cmd_list, "List models or output files"),
    "ls": ("list", cmd_list, ""),
    "quit": ("exit", lambda _: sys.exit(0), "Exit"),
    "exit": ("quit", lambda _: sys.exit(0), ""),
    "q": ("quit", lambda _: sys.exit(0), ""),
}

ALIASES: dict[str, str] = {}
for canonical, (alias, _func, _desc) in COMMANDS.items():
    if alias and alias != canonical:
        ALIASES[alias] = canonical


def _print_banner() -> None:
    print(flush=True)
    print("═" * 60, flush=True)
    print("  Interactive Mode", flush=True)
    print("═" * 60, flush=True)
    print("  Type 'help' for commands, 'quit' to exit.", flush=True)
    print("═" * 60, flush=True)
    print(flush=True)


def start_interactive(session_state: dict[str, Any], output_dir: str | None = None) -> None:
    global SESSION_STATE, OUTPUT_DIR
    SESSION_STATE = session_state
    OUTPUT_DIR = output_dir

    _print_banner()

    try:
        import readline
        import atexit

        histfile = os.path.join(os.path.expanduser("~"), ".vidrev_history")
        try:
            readline.read_history_file(histfile)
            readline.set_history_length(100)
        except FileNotFoundError:
            pass
        atexit.register(readline.write_history_file, histfile)
    except ImportError:
        pass

    while True:
        try:
            raw = input("vidrev> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(flush=True)
            break

        if not raw:
            continue

        parts = raw.split()
        cmd_name = parts[0].lower()
        cmd_args = parts[1:]

        resolved = ALIASES.get(cmd_name, cmd_name)
        entry = COMMANDS.get(resolved)

        if entry is None:
            print(f"  Unknown command: {cmd_name}. Type 'help' for available commands.", flush=True)
            continue

        _canonical, func, _desc = entry
        try:
            func(cmd_args)
        except Exception as exc:
            print(f"  Command error: {exc}", flush=True)

    print("  Goodbye!", flush=True)
