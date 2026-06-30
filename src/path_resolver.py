from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent


def get_root() -> str:
    return str(_ROOT)


def get_config_path(filename: str) -> str:
    return str(_ROOT / "config" / filename)


def get_output_path(filename: str = "") -> str:
    env_path = os.environ.get("VIDEO_REV_OUTPUT_DIR", str(_ROOT / "output_blueprints"))
    return os.path.join(env_path, filename)


def normalize_for_env(target: str | Any, wsl_mode: str | None = None) -> str | Any:
    if not isinstance(target, str):
        return target
    if "://" in target:
        return target

    is_unc = target.startswith("\\\\")
    if is_unc:
        unc_path = target.replace("\\\\", "/").replace("\\", "/")
        parts = [p for p in unc_path.split("/") if p]
        if len(parts) >= 2:
            return f"/mnt/{parts[0].lower()}/{'/'.join(parts[1:])}"

    import re

    env = wsl_mode
    if env is None:
        from utils.cli import detect_environment

        env = detect_environment()

    if env == "win":
        # Don't mangle Unix-style paths (WSL interop, test fixtures)
        if target.startswith("/"):
            return target
        return os.path.abspath(target)

    is_windows_path = bool(re.match(r"^[a-zA-Z]:[\\/]", target))
    if is_windows_path:
        drive = target[0].lower()
        posix_path = target[2:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{posix_path}"

    m = re.match(r"^/mnt/([a-z])/", target, re.IGNORECASE)
    if m:
        return f"/mnt/{m.group(1).lower()}/{target[len(m.group(0)) :]}"

    return os.path.abspath(target)
