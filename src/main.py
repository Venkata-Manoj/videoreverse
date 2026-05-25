#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys

import os

from src.batch import run_batch_pipeline
from src.pipeline import run_pipeline
from utils.cli import detect_environment, parse_cli_args, print_help
from utils.compare import compare_outputs, print_comparison
from utils.error_codes import VRError, VRErrorCode, explain_error, print_error_report
from utils.interactive import start_interactive
from utils.logger import error, info, set_log_level


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_help()
        sys.exit(0)

    if "--explain-error" in args:
        idx = args.index("--explain-error")
        if idx + 1 < len(args) and args[idx + 1]:
            code = args[idx + 1].upper()
            print(explain_error(code))
        else:
            print("Usage: --explain-error <VR-CODE>")
            print("Example: --explain-error VR-101")
            print("\nCommon error codes:")
            for vrc in VRErrorCode:
                print(f"  {vrc.code} — {vrc.message}")
        sys.exit(0)

    is_batch = "--batch" in args
    non_flag_args = [a for a in args if not a.startswith("-")]
    if not is_batch and len(non_flag_args) == 0:
        print("Usage: python -m src.main <video_path_or_url> [options]", file=sys.stderr)
        print("       python -m src.main --batch <file_or_dir> [options]", file=sys.stderr)
        print("       python -m src.main --help  for all options", file=sys.stderr)
        print("       python -m src.main --explain-error <VR-CODE> for troubleshooting", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  python -m src.main ./video.mp4", file=sys.stderr)
        print("  python -m src.main E:\\vidrev\\video.mp4", file=sys.stderr)
        print("  python -m src.main https://example.com/video.mp4", file=sys.stderr)
        print("  python -m src.main --batch ./videos/", file=sys.stderr)
        print("  python -m src.main --batch video_list.txt", file=sys.stderr)
        sys.exit(1)

    options = parse_cli_args(args)

    if options.get("verbose"):
        set_log_level("debug")
    if options.get("quiet"):
        set_log_level("quiet")
    if options.get("log_level"):
        set_log_level(options["log_level"])

    profile = options.get("profile")
    if profile:
        info("main", f"Profile active: {profile}")

    info("main", "VideoReverse starting...")
    info("main", f"Environment: {detect_environment()}")

    try:
        if options.get("batch"):
            info("main", f"Batch mode: {options['batch']}")
            output = asyncio.run(
                run_batch_pipeline(
                    options["batch"],
                    options,
                    max_parallel=options.get("parallel", 4),
                )
            )
        else:
            info("main", f"Video path: {options['video_path']}")
            output = asyncio.run(run_pipeline(options))

            if options.get("dry_run") and options.get("log_level") != "quiet":
                print("\n" + "═" * 60, flush=True)
                print("  DRY RUN — No files saved", flush=True)
                print("═" * 60 + "\n", flush=True)

        if options.get("compare_video"):
            info("main", f"Compare mode: comparing with {options['compare_video']}")
            compare_opts = dict(options)
            compare_opts["video_path"] = compare_opts["compare_video"]
            compare_output = asyncio.run(run_pipeline(compare_opts))
            result = compare_outputs(output, compare_output)
            if options.get("log_level") != "quiet":
                print_comparison(result)
            output_dir = options.get("output_dir") or "output_blueprints"
            os.makedirs(output_dir, exist_ok=True)
            comp_path = os.path.join(output_dir, f"compare_{options.get('video_path', 'unknown')}.json")
            with open(comp_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            info("main", f"Comparison saved to {comp_path}")
            sys.exit(0)

        if options.get("interactive") and not options.get("batch"):
            if options.get("log_level") != "quiet":
                print(json.dumps(output, indent=2), flush=True)
            session = {
                "blueprint": output.get("blueprint"),
                "prompts": output.get("prompts"),
                "video_metadata": output.get("video_metadata"),
                "full_output": output,
            }
            start_interactive(session, options.get("output_dir"))
        else:
            if options.get("log_level") != "quiet":
                print(json.dumps(output, indent=2), flush=True)

        sys.exit(0)
    except VRError as err:
        error("main", f"[{err.code}] {err.message}")
        if err.detail:
            error("main", f"  Detail: {err.detail}")
        print_error_report(err.code_obj, err.detail)
        sys.exit(1)
    except Exception as err:
        error("main", f"Fatal error: {err}")
        print(f"\n  ❌ Unexpected error: {err}", flush=True)
        print(f"  Run with --explain-error VR-499 for troubleshooting\n", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
