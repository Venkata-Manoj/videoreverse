#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys

from src.pipeline import run_pipeline
from utils.cli import detect_environment, parse_cli_args, print_help
from utils.logger import error, info, set_log_level


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_help()
        sys.exit(0)

    if len(args) == 0 or not args[0] or args[0].startswith("-"):
        print("Usage: python -m src.main <video_path_or_url> [options]", file=sys.stderr)
        print("       python -m src.main --help  for all options", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  python -m src.main ./video.mp4", file=sys.stderr)
        print("  python -m src.main E:\\vidrev\\video.mp4", file=sys.stderr)
        print("  python -m src.main https://example.com/video.mp4", file=sys.stderr)
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
    info("main", f"Video path: {options['video_path']}")

    try:
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
