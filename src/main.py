#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys

from src.batch import run_batch_pipeline
from src.pipeline import run_pipeline
from utils.cli import detect_environment, parse_cli_args, print_help
from utils.logger import error, info, set_log_level


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_help()
        sys.exit(0)

    is_batch = "--batch" in args
    if not is_batch and (len(args) == 0 or not args[0] or args[0].startswith("-")):
        print("Usage: python -m src.main <video_path_or_url> [options]", file=sys.stderr)
        print("       python -m src.main --batch <file_or_dir> [options]", file=sys.stderr)
        print("       python -m src.main --help  for all options", file=sys.stderr)
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

            if options.get("dry_run"):
                print("\n" + "═" * 60, flush=True)
                print("  DRY RUN — No files saved", flush=True)
                print("═" * 60 + "\n", flush=True)

        if options.get("log_level") != "quiet":
            print(json.dumps(output, indent=2), flush=True)

        sys.exit(0)
    except Exception as err:
        error("main", f"Fatal error: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
