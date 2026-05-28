from __future__ import annotations

import asyncio
import json
import sys

from dotenv import load_dotenv

from src.pipeline import run_pipeline
from utils.cli import detect_environment, parse_cli_args, print_help
from utils.error_codes import VRError
from utils.logger import error, info, set_log_level


def main() -> None:
    load_dotenv()
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_help()
        sys.exit(0)

    non_flag_args = [a for a in args if not a.startswith("-")]
    if len(non_flag_args) == 0:
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

    try:
        info("main", f"Video path: {options['video_path']}")
        output = asyncio.run(run_pipeline(options))

        if options.get("log_level") != "quiet":
            print(json.dumps(output, indent=2), flush=True)

        sys.exit(0)
    except VRError as err:
        error("main", f"[{err.code}] {err.message}")
        if err.detail:
            error("main", f"  Detail: {err.detail}")
        sys.exit(1)
    except Exception as err:
        error("main", f"Fatal error: {err}")
        print(f"\n  Error: {err}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
