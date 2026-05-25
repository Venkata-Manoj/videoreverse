#!/usr/bin/env python3
"""CLI tool to display pipeline history metrics from pipeline_history.jsonl."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# Ensure project root is on path
PROJECT_ROOT = None
for p in (__file__, sys.argv[0] if sys.argv else ""):
    d = __import__("os").path.dirname(__import__("os").path.abspath(p))
    if __import__("os").path.exists(__import__("os").path.join(d, "src", "main.py")):
        PROJECT_ROOT = d
        break
if PROJECT_ROOT is None:
    PROJECT_ROOT = __import__("os").path.abspath(
        __import__("os").path.join(__import__("os").path.dirname(__file__), "..")
    )
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.metrics import (
    PIPELINE_HISTORY_FILE,
    compute_summary,
    export_metrics_json,
    load_pipeline_history,
)


def _fmt_ms(ms: float | None) -> str:
    if ms is None:
        return "-"
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms:.0f}ms"


def _print_summary(summary: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("  VideoReverse — Pipeline Metrics Summary")
    print("=" * 60)

    print(f"\n  Overview:")
    print(f"    Pipeline runs:    {summary['total_pipeline_runs']}")
    print(f"    Old step entries: {summary['total_old_step_entries']}")
    print(f"    Total entries:    {summary['total_history_entries']}")

    if summary["total_pipeline_runs"] == 0:
        print("\n  No v2 pipeline runs recorded yet.")
        return

    print(f"\n  Success / Failure:")
    print(f"    Successful:  {summary['successful_runs']}")
    print(f"    Failed:      {summary['failed_runs']}")
    print(f"    Success rate: {summary['success_rate']}%")

    print(f"\n  Fallback:")
    print(f"    Total:  {summary['total_fallbacks']}")
    print(f"    Rate:   {summary['fallback_rate']}%")

    print(f"\n  Cache:")
    print(f"    Hits:  {summary['total_cache_hits']}")
    print(f"    Rate:  {summary['cache_hit_rate']}%")

    print(f"\n  Retries & Errors:")
    print(f"    Total retries:  {summary['total_retries']}")
    print(f"    Total errors:   {summary['total_errors']}")

    print(f"\n  Models & Shots:")
    print(f"    Models compiled: {summary['total_models_compiled']}")
    print(f"    Shots detected:  {summary['total_shots_detected']}")

    avg = summary.get("average_timing_ms") or {}
    if avg:
        print(f"\n  Average Timing per Step:")
        for step in ("ingest_ms", "synthesize_ms", "compile_ms", "total_ms"):
            label = step.replace("_ms", "").capitalize()
            print(f"    {label}: {_fmt_ms(avg.get(step))}")

    fastest = summary.get("fastest_pipeline_ms")
    slowest = summary.get("slowest_pipeline_ms")
    if fastest is not None or slowest is not None:
        print(f"\n  Pipeline Duration:")
        if fastest is not None:
            print(f"    Fastest: {_fmt_ms(fastest)}")
        if slowest is not None:
            print(f"    Slowest: {_fmt_ms(slowest)}")

    print(f"\n  Last updated: {summary.get('last_updated', '-')}")
    print("=" * 60 + "\n")


def _list_entries(args: argparse.Namespace) -> None:
    entries = load_pipeline_history()
    if not entries:
        print("  No pipeline history entries found.")
        return

    v2 = [e for e in entries if e.get("version") == "2.0"]
    old = [e for e in entries if e.get("version") != "2.0"]

    print(f"\n  Total entries: {len(entries)} ({len(v2)} pipeline runs, {len(old)} old step entries)")

    if args.v2_only or not args.all:
        show = v2
    else:
        show = entries

    limit = args.limit or len(show)
    for entry in show[-limit:]:
        ts = entry.get("timestamp", "?")[:19]
        if entry.get("version") == "2.0":
            dur = _fmt_ms(entry.get("timing_ms", {}).get("total_ms"))
            ok = "✅" if entry.get("success") else "❌"
            fb = " ⚠️" if entry.get("fallback", {}).get("active") else ""
            vid = (entry.get("video_path") or "?").split("/")[-1]
            print(f"  {ok} {ts} | {dur} | {entry.get('models_compiled', '?')} models | {vid}{fb}")
        else:
            ok = "✅" if entry.get("success") else "❌"
            print(f"  {ok} {ts} | step={entry.get('step', '?')} | {_fmt_ms(entry.get('duration_ms'))}")
    print()


def _show_detail(args: argparse.Namespace) -> None:
    entries = load_pipeline_history()
    v2 = [e for e in entries if e.get("version") == "2.0"]
    if not v2:
        print("  No pipeline runs found.")
        return

    if args.index is not None:
        idx = args.index
        if idx < 0 or idx >= len(v2):
            print(f"  Index {idx} out of range. Total pipeline runs: {len(v2)}")
            return
        entry = v2[idx]
    else:
        entry = v2[-1]

    print("\n" + "=" * 60)
    print("  Pipeline Run Detail")
    print("=" * 60)
    print(f"  Timestamp:    {entry.get('timestamp', '?')}")
    print(f"  Video:        {entry.get('video_path', '?')}")
    print(f"  Video type:   {entry.get('video_type', '?')}")
    print(f"  Duration:     {entry.get('video_duration_seconds', '?')}s")
    print(f"  Success:      {'✅' if entry.get('success') else '❌'}")
    print(f"  Gemini model: {entry.get('gemini_model', '?')}")
    print(f"  Sample mode:  {entry.get('sample_mode', '?')}")
    print(f"  Max duration: {entry.get('max_duration', '?')}")
    print(f"  Models req:   {entry.get('models_requested')}")

    timing = entry.get("timing_ms") or {}
    if timing:
        print(f"\n  Timing:")
        for k, v in sorted(timing.items()):
            print(f"    {k}: {_fmt_ms(v)}")

    fb = entry.get("fallback") or {}
    print(f"\n  Fallback:  {'⚠️ ' + fb.get('reason', 'yes') if fb.get('active') else 'No'}")
    cache = entry.get("cache") or {}
    print(f"  Cache hit: {'✅' if cache.get('hit') else 'No'}")
    print(f"  Retries:   {entry.get('retries', 0)}")

    errors = entry.get("errors") or []
    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for err in errors:
            print(f"    [{err.get('step', '?')}] {err.get('error', '?')}")

    print(f"  Shots:       {entry.get('shots_detected', '?')}")
    print(f"  Models out:  {entry.get('models_compiled', '?')}")
    print("=" * 60 + "\n")


def _export_json(args: argparse.Namespace) -> None:
    if args.output:
        path = export_metrics_json(args.output)
        print(f"  Metrics exported to {args.output}")
    else:
        print(export_metrics_json())
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="View pipeline history and metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/stats.py              Show summary\n"
            "  python scripts/stats.py list          List recent pipeline runs\n"
            "  python scripts/stats.py list --all    Show all entries including old\n"
            "  python scripts/stats.py detail        Show latest pipeline run details\n"
            "  python scripts/stats.py detail -i 0   Show first pipeline run details\n"
            "  python scripts/stats.py export        Export all metrics as JSON\n"
        ),
    )

    sub = parser.add_subparsers(dest="command", help="Sub-command")

    list_parser = sub.add_parser("list", help="List pipeline history entries")
    list_parser.add_argument("--limit", "-n", type=int, default=10, help="Max entries to show")
    list_parser.add_argument("--all", "-a", action="store_true", help="Show old step entries too")
    list_parser.add_argument("--v2-only", action="store_true", default=True, help="Show only v2 pipeline entries (default)")

    detail_parser = sub.add_parser("detail", help="Show details of a specific pipeline run")
    detail_parser.add_argument("--index", "-i", type=int, default=None, help="Index of run (0-based, default: latest)")

    export_parser = sub.add_parser("export", help="Export metrics as JSON")
    export_parser.add_argument("--output", "-o", type=str, default=None, help="Output file path")

    args = parser.parse_args()

    if args.command == "list":
        _list_entries(args)
    elif args.command == "detail":
        _show_detail(args)
    elif args.command == "export":
        _export_json(args)
    else:
        summary = compute_summary()
        _print_summary(summary)


if __name__ == "__main__":
    main()
