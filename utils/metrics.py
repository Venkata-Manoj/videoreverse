from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from typing import Any

from src.path_resolver import get_output_path

LOG_DIR = get_output_path()


def _ensure_log_dir() -> None:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)


PIPELINE_HISTORY_FILE = os.path.join(LOG_DIR, "pipeline_history.jsonl")


def clear_history() -> None:
    if os.path.exists(PIPELINE_HISTORY_FILE):
        os.unlink(PIPELINE_HISTORY_FILE)


def _format_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _now_ms() -> float:
    return time.time() * 1000


class PipelineMetrics:
    def __init__(self, options: dict[str, Any] | None = None) -> None:
        if options is None:
            options = {}
        self._start_ms = _now_ms()
        self._step_start: dict[str, float] = {}
        self.timing_ms: dict[str, float] = {}
        self.errors: list[dict[str, str]] = []
        self.success = True
        self.fallback_active = False
        self.fallback_reason: str | None = None
        self.cache_hit = False
        self.cache_key: str | None = None
        self.retries = 0
        self.models_compiled = 0
        self.shots_detected = 0
        self.video_path: str | None = options.get("video_path")
        self.video_type: str | None = None
        self.video_duration: float | None = None
        self.gemini_model: str | None = options.get("gemini_model")
        self.sample_mode: str | None = options.get("sample_mode")
        self.max_duration: float | None = options.get("max_duration")
        self.models_requested: list[str] | None = options.get("models")

    def start_step(self, name: str) -> None:
        self._step_start[name] = _now_ms()

    def end_step(self, name: str) -> float:
        ms = _now_ms() - self._step_start.pop(name, _now_ms())
        self.timing_ms[f"{name}_ms"] = round(ms, 1)
        return ms

    def record_error(self, step: str, error: str) -> None:
        self.errors.append({"step": step, "error": error})

    def to_record(self) -> dict[str, Any]:
        self.timing_ms.setdefault("total_ms", round(_now_ms() - self._start_ms, 1))
        return {
            "version": "2.0",
            "timestamp": _format_timestamp(),
            "video_path": self.video_path,
            "video_type": self.video_type,
            "video_duration_seconds": self.video_duration,
            "success": self.success,
            "timing_ms": dict(self.timing_ms),
            "fallback": {
                "active": self.fallback_active,
                "reason": self.fallback_reason,
            },
            "cache": {
                "hit": self.cache_hit,
                "key": self.cache_key,
            },
            "errors": list(self.errors),
            "retries": self.retries,
            "models_compiled": self.models_compiled,
            "shots_detected": self.shots_detected,
            "gemini_model": self.gemini_model,
            "sample_mode": self.sample_mode,
            "max_duration": self.max_duration,
            "models_requested": self.models_requested,
        }

    def write(self) -> dict[str, Any]:
        record = self.to_record()
        _ensure_log_dir()
        try:
            with open(PIPELINE_HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass
        return record

    @property
    def elapsed_seconds(self) -> float:
        return (_now_ms() - self._start_ms) / 1000


def _parse_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def load_pipeline_history(max_entries: int | None = None) -> list[dict[str, Any]]:
    if not os.path.exists(PIPELINE_HISTORY_FILE):
        return []
    entries: list[dict[str, Any]] = []
    try:
        with open(PIPELINE_HISTORY_FILE, encoding="utf-8") as f:
            for line in f:
                parsed = _parse_line(line)
                if parsed:
                    entries.append(parsed)
    except Exception:
        return entries
    if max_entries is not None and len(entries) > max_entries:
        entries = entries[-max_entries:]
    return entries


def _is_v2_entry(entry: dict[str, Any]) -> bool:
    return entry.get("version") == "2.0"


def compute_summary(entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if entries is None:
        entries = load_pipeline_history()

    v2_entries = [e for e in entries if _is_v2_entry(e)]
    old_entries = [e for e in entries if not _is_v2_entry(e)]

    total_pipelines = len(v2_entries)
    successful_pipelines = sum(1 for e in v2_entries if e.get("success"))
    failed_pipelines = total_pipelines - successful_pipelines
    total_fallbacks = sum(1 for e in v2_entries if e.get("fallback", {}).get("active"))
    total_cache_hits = sum(1 for e in v2_entries if e.get("cache", {}).get("hit"))
    total_old_step_entries = len(old_entries)

    timing_fields = ["ingest_ms", "synthesize_ms", "compile_ms", "total_ms"]
    timing_sums: dict[str, float] = {f: 0.0 for f in timing_fields}
    timing_counts: dict[str, int] = {f: 0 for f in timing_fields}
    timing_mins: dict[str, float] = {}
    timing_maxs: dict[str, float] = {}

    for e in v2_entries:
        t = e.get("timing_ms") or {}
        for f in timing_fields:
            val = t.get(f)
            if val is not None:
                timing_sums[f] += val
                timing_counts[f] += 1
                if f not in timing_mins or val < timing_mins[f]:
                    timing_mins[f] = val
                if f not in timing_maxs or val > timing_maxs[f]:
                    timing_maxs[f] = val

    avg_timing: dict[str, float] = {}
    for f in timing_fields:
        if timing_counts[f]:
            avg_timing[f] = round(timing_sums[f] / timing_counts[f], 1)

    total_retries = sum(e.get("retries", 0) for e in v2_entries)
    total_errors_list = sum(len(e.get("errors") or []) for e in v2_entries)
    total_models = sum(e.get("models_compiled", 0) for e in v2_entries)
    total_shots = sum(e.get("shots_detected", 0) for e in v2_entries)

    pipeline_durations = [e.get("timing_ms", {}).get("total_ms", 0) for e in v2_entries if e.get("timing_ms")]

    return {
        "total_pipeline_runs": total_pipelines,
        "total_old_step_entries": total_old_step_entries,
        "total_history_entries": len(entries),
        "successful_runs": successful_pipelines,
        "failed_runs": failed_pipelines,
        "success_rate": round(successful_pipelines / total_pipelines * 100, 1) if total_pipelines else 0.0,
        "total_fallbacks": total_fallbacks,
        "fallback_rate": round(total_fallbacks / total_pipelines * 100, 1) if total_pipelines else 0.0,
        "total_cache_hits": total_cache_hits,
        "cache_hit_rate": round(total_cache_hits / total_pipelines * 100, 1) if total_pipelines else 0.0,
        "total_retries": total_retries,
        "total_errors": total_errors_list,
        "total_models_compiled": total_models,
        "total_shots_detected": total_shots,
        "average_timing_ms": avg_timing,
        "min_timing_ms": timing_mins if timing_mins else None,
        "max_timing_ms": timing_maxs if timing_maxs else None,
        "slowest_pipeline_ms": max(pipeline_durations) if pipeline_durations else None,
        "fastest_pipeline_ms": min(pipeline_durations) if pipeline_durations else None,
        "last_updated": _format_timestamp(),
    }


def export_metrics_json(output_path: str | None = None) -> str:
    entries = load_pipeline_history()
    summary = compute_summary(entries)
    export = {
        "summary": summary,
        "entries": entries,
    }
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2)
    return json.dumps(export, indent=2)
