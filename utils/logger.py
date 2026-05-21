from __future__ import annotations

import json
import os
from datetime import UTC
from typing import Any

from src.path_resolver import get_output_path

LOG_DIR = get_output_path()
ERROR_LOG_PATH = os.path.join(LOG_DIR, "errors.log")


class LogLevel:
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3
    QUIET = 4


_current_log_level: int = LogLevel.INFO


def set_log_level(level: str | int) -> None:
    global _current_log_level
    if isinstance(level, str):
        mapping = {
            "debug": LogLevel.DEBUG,
            "info": LogLevel.INFO,
            "warn": LogLevel.WARN,
            "error": LogLevel.ERROR,
            "quiet": LogLevel.QUIET,
            "silent": LogLevel.QUIET,
        }
        _current_log_level = mapping.get(level.lower(), LogLevel.INFO)
    else:
        _current_log_level = level


def get_log_level() -> int:
    return _current_log_level


def should_log(level: int) -> bool:
    return level >= _current_log_level


def _format_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(UTC).isoformat()


def _ensure_log_dir() -> None:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)


def log(level: int, category: str, message: str, data: Any = None) -> None:
    if not should_log(level):
        return

    timestamp = _format_timestamp()
    level_names = ["DEBUG", "INFO", "WARN", "ERROR"]
    level_name = level_names[level] if level < len(level_names) else "UNKNOWN"

    formatted = f"[{timestamp}] [{level_name}] [{category}] {message}"

    if level >= LogLevel.ERROR:
        print(formatted, flush=True)
    else:
        print(formatted, flush=True)

    if data is not None:
        data_str = json.dumps(data, indent=2) if isinstance(data, dict) else str(data)
        print(data_str, flush=True)

    if level >= LogLevel.ERROR:
        _append_to_error_log(formatted, data)


def debug(category: str, message: str, data: Any = None) -> None:
    log(LogLevel.DEBUG, category, message, data)


def info(category: str, message: str, data: Any = None) -> None:
    log(LogLevel.INFO, category, message, data)


def warn(category: str, message: str, data: Any = None) -> None:
    log(LogLevel.WARN, category, message, data)


def error(category: str, message: str, data: Any = None) -> None:
    log(LogLevel.ERROR, category, message, data)


def _append_to_error_log(message: str, data: Any = None) -> None:
    _ensure_log_dir()
    try:
        log_entry = message
        if data is not None:
            log_entry += "\n  Data: " + (json.dumps(data) if isinstance(data, dict) else str(data))
        log_entry += "\n"
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as err:
        print(f"Failed to write to error log: {err}", flush=True)


def get_error_log() -> list[str]:
    _ensure_log_dir()
    if not os.path.exists(ERROR_LOG_PATH):
        return []
    try:
        with open(ERROR_LOG_PATH, encoding="utf-8") as f:
            content = f.read()
        return [line for line in content.split("\n") if line.strip()]
    except Exception:
        return []


def clear_error_log() -> None:
    _ensure_log_dir()
    if os.path.exists(ERROR_LOG_PATH):
        os.unlink(ERROR_LOG_PATH)


def log_pipeline_step(
    step_name: str,
    duration: float,
    success: bool = True,
    error: Exception | str | None = None,
) -> dict[str, Any]:
    entry = {
        "timestamp": _format_timestamp(),
        "step": step_name,
        "duration_ms": duration,
        "success": success,
        "error": str(error) if error else None,
    }

    _ensure_log_dir()
    log_file = os.path.join(LOG_DIR, "pipeline_history.jsonl")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as err:
        print(f"Failed to write pipeline history: {err}", flush=True)

    return entry
