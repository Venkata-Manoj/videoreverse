from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

from tests.unit.test_framework import expect, it

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
import sys

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.metrics import (
    PIPELINE_HISTORY_FILE,
    PipelineMetrics,
    clear_history,
    compute_summary,
    export_metrics_json,
    load_pipeline_history,
)

# Start with a clean history for tests
clear_history()


def _make_metrics(**overrides: dict) -> PipelineMetrics:
    opts = {
        "video_path": "/videos/test.mp4",
        "gemini_model": "gemini-2.5-flash",
        "sample_mode": "first-n",
        "max_duration": 30.0,
        "models": None,
    }
    opts.update(overrides)
    return PipelineMetrics(opts)


def _write_history(entries: list[dict]) -> str:
    path = PIPELINE_HISTORY_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path


# =======================
# PipelineMetrics
# =======================

def _tracks_timing() -> None:
    m = _make_metrics()
    m.start_step("ingest")
    m.end_step("ingest")
    expect("ingest_ms" in m.timing_ms).to_be(True)
    expect(m.timing_ms["ingest_ms"]).to_be_instance(float)

it("tracks timing with start/end step", _tracks_timing)


def _tracks_errors() -> None:
    m = _make_metrics()
    m.record_error("ingest", "something broke")
    expect(len(m.errors)).to_be(1)
    expect(m.errors[0]["step"]).to_be("ingest")
    expect(m.errors[0]["error"]).to_be("something broke")

it("tracks errors", _tracks_errors)


def _tracks_fallback() -> None:
    m = _make_metrics()
    expect(m.fallback_active).to_be(False)
    m.fallback_active = True
    m.fallback_reason = "API down"
    record = m.to_record()
    expect(record["fallback"]["active"]).to_be(True)
    expect(record["fallback"]["reason"]).to_be("API down")

it("tracks fallback state", _tracks_fallback)


def _tracks_cache() -> None:
    m = _make_metrics()
    m.cache_hit = True
    m.cache_key = "abc123"
    record = m.to_record()
    expect(record["cache"]["hit"]).to_be(True)
    expect(record["cache"]["key"]).to_be("abc123")

it("tracks cache hit", _tracks_cache)


def _tracks_retries() -> None:
    m = _make_metrics()
    m.retries = 3
    record = m.to_record()
    expect(record["retries"]).to_be(3)

it("tracks retries", _tracks_retries)


def _tracks_models_and_shots() -> None:
    m = _make_metrics()
    m.models_compiled = 8
    m.shots_detected = 5
    record = m.to_record()
    expect(record["models_compiled"]).to_be(8)
    expect(record["shots_detected"]).to_be(5)

it("tracks models and shots", _tracks_models_and_shots)


def _record_has_version() -> None:
    m = _make_metrics()
    record = m.to_record()
    expect(record["version"]).to_be("2.0")

it("record has version 2.0", _record_has_version)


def _record_has_timestamp() -> None:
    m = _make_metrics()
    record = m.to_record()
    expect("timestamp" in record).to_be(True)
    expect(len(record["timestamp"])).to_be_greater_than(10)

it("record has timestamp", _record_has_timestamp)


def _includes_options() -> None:
    m = _make_metrics()
    record = m.to_record()
    expect(record["video_path"]).to_be("/videos/test.mp4")
    expect(record["gemini_model"]).to_be("gemini-2.5-flash")
    expect(record["sample_mode"]).to_be("first-n")
    expect(record["max_duration"]).to_be(30.0)

it("includes CLI options in record", _includes_options)


def _writes_to_history_file() -> None:
    clear_history()
    m = _make_metrics()
    m.models_compiled = 4
    m.shots_detected = 2
    m.success = True
    record = m.write()
    expect(os.path.exists(PIPELINE_HISTORY_FILE)).to_be(True)
    with open(PIPELINE_HISTORY_FILE, encoding="utf-8") as f:
        line = f.readline().strip()
    parsed = json.loads(line)
    expect(parsed["version"]).to_be("2.0")
    expect(parsed["models_compiled"]).to_be(4)
    expect(parsed["shots_detected"]).to_be(2)

it("write appends to pipeline_history.jsonl", _writes_to_history_file)


def _appends_multiple_records() -> None:
    clear_history()
    m1 = _make_metrics()
    m1.models_compiled = 3
    m1.write()

    m2 = _make_metrics()
    m2.models_compiled = 5
    m2.write()

    entries = load_pipeline_history()
    v2 = [e for e in entries if e.get("version") == "2.0"]
    expect(len(v2)).to_be(2)
    expect(v2[-1]["models_compiled"]).to_be(5)

it("appends multiple records", _appends_multiple_records)


def _elapsed_seconds_increases() -> None:
    m = _make_metrics()
    e1 = m.elapsed_seconds
    import time
    time.sleep(0.01)
    e2 = m.elapsed_seconds
    expect(e2).to_be_greater_than(e1)

it("elapsed_seconds increases over time", _elapsed_seconds_increases)


# =======================
# load_pipeline_history
# =======================

def _loads_v2_entries() -> None:
    _write_history([
        {"version": "2.0", "timestamp": "2026-01-01T00:00:00", "success": True},
        {"version": "2.0", "timestamp": "2026-01-02T00:00:00", "success": False},
    ])
    entries = load_pipeline_history()
    expect(len(entries)).to_be(2)

it("loads v2 entries", _loads_v2_entries)


def _loads_old_step_entries() -> None:
    _write_history([
        {"step": "ingest", "duration_ms": 100, "success": True},
        {"step": "synthesize", "duration_ms": 500, "success": True},
    ])
    entries = load_pipeline_history()
    expect(len(entries)).to_be(2)
    expect(entries[0]["step"]).to_be("ingest")

it("loads old per-step entries", _loads_old_step_entries)


def _handles_empty_history() -> None:
    if os.path.exists(PIPELINE_HISTORY_FILE):
        os.unlink(PIPELINE_HISTORY_FILE)
    entries = load_pipeline_history()
    expect(entries).to_be([])

it("handles empty history", _handles_empty_history)


def _skips_corrupted_lines() -> None:
    path = _write_history([{"version": "2.0", "success": True}])
    with open(path, "a", encoding="utf-8") as f:
        f.write("not json\n")
        f.write('{"version": "2.0", "success": false}\n')
    entries = load_pipeline_history()
    expect(len(entries)).to_be(2)

it("skips corrupted lines", _skips_corrupted_lines)


def _respects_max_entries() -> None:
    entries_list = [{"version": "2.0", "idx": i} for i in range(20)]
    _write_history(entries_list)
    loaded = load_pipeline_history(max_entries=5)
    expect(len(loaded)).to_be(5)
    expect(loaded[0]["idx"]).to_be(15)

it("respects max_entries param", _respects_max_entries)


# =======================
# compute_summary
# =======================

def _summary_with_v2_entries() -> None:
    _write_history([
        {"version": "2.0", "success": True, "timing_ms": {"total_ms": 5000}, "fallback": {"active": False}, "cache": {"hit": True}, "retries": 0, "errors": [], "models_compiled": 8, "shots_detected": 4},
        {"version": "2.0", "success": True, "timing_ms": {"total_ms": 8000}, "fallback": {"active": False}, "cache": {"hit": False}, "retries": 1, "errors": [], "models_compiled": 6, "shots_detected": 3},
        {"version": "2.0", "success": False, "timing_ms": {"total_ms": 3000}, "fallback": {"active": True, "reason": "API error"}, "cache": {"hit": False}, "retries": 3, "errors": [{"step": "synthesize", "error": "fail"}], "models_compiled": 0, "shots_detected": 0},
        {"step": "ingest", "duration_ms": 100, "success": True},
    ])
    summary = compute_summary()
    expect(summary["total_pipeline_runs"]).to_be(3)
    expect(summary["total_old_step_entries"]).to_be(1)
    expect(summary["total_history_entries"]).to_be(4)
    expect(summary["successful_runs"]).to_be(2)
    expect(summary["failed_runs"]).to_be(1)
    expect(summary["success_rate"]).to_be(66.7)
    expect(summary["total_fallbacks"]).to_be(1)
    expect(summary["fallback_rate"]).to_be(33.3)
    expect(summary["total_cache_hits"]).to_be(1)
    expect(summary["cache_hit_rate"]).to_be(33.3)
    expect(summary["total_retries"]).to_be(4)
    expect(summary["total_errors"]).to_be(1)
    expect(summary["total_models_compiled"]).to_be(14)
    expect(summary["total_shots_detected"]).to_be(7)
    avg_total = summary["average_timing_ms"].get("total_ms")
    expect(avg_total).to_be(round((5000 + 8000 + 3000) / 3, 1))

it("computes summary from v2 entries", _summary_with_v2_entries)


def _summary_with_empty_entries() -> None:
    if os.path.exists(PIPELINE_HISTORY_FILE):
        os.unlink(PIPELINE_HISTORY_FILE)
    summary = compute_summary()
    expect(summary["total_pipeline_runs"]).to_be(0)
    expect(summary["success_rate"]).to_be(0.0)
    expect(summary["fallback_rate"]).to_be(0.0)
    expect(summary["cache_hit_rate"]).to_be(0.0)

it("summary handles empty entries", _summary_with_empty_entries)


def _summary_handles_missing_fields() -> None:
    _write_history([
        {"version": "2.0", "success": True},
        {"version": "2.0", "success": True, "timing_ms": {"synthesize_ms": 100}},
    ])
    summary = compute_summary()
    expect(summary["total_pipeline_runs"]).to_be(2)
    expect(summary["average_timing_ms"].get("synthesize_ms")).to_be(100.0)
    expect(summary["average_timing_ms"].get("ingest_ms")).to_be(None)

it("summary handles missing timing fields", _summary_handles_missing_fields)


# =======================
# export_metrics_json
# =======================

def _exports_json() -> None:
    _write_history([{"version": "2.0", "success": True}])
    out = export_metrics_json()
    parsed = json.loads(out)
    expect("summary" in parsed).to_be(True)
    expect("entries" in parsed).to_be(True)
    expect(parsed["summary"]["total_pipeline_runs"]).to_be(1)
    expect(len(parsed["entries"])).to_be(1)

it("exports metrics as JSON string", _exports_json)


def _exports_to_file() -> None:
    _write_history([{"version": "2.0", "success": True}])
    tmp = os.path.join(tempfile.gettempdir(), "vidrev_test_metrics_export.json")
    try:
        result = export_metrics_json(tmp)
        expect(os.path.exists(tmp)).to_be(True)
        with open(tmp, encoding="utf-8") as f:
            parsed = json.load(f)
        expect(parsed["summary"]["total_pipeline_runs"]).to_be(1)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

it("exports metrics to file", _exports_to_file)
