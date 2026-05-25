from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from typing import Any

from src.compile import get_template_version


def _sanitize_video_name(video_path: str) -> str:
    normalized = video_path.replace("\\", "/")
    name = os.path.splitext(os.path.basename(normalized))[0]
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    return name.strip("_") or "unknown"


def _history_dir(video_name: str, output_dir: str) -> str:
    return os.path.join(output_dir, video_name, "history")


def _version_file(video_name: str, output_dir: str, version: int) -> str:
    return os.path.join(_history_dir(video_name, output_dir), f"v{version}.json")


def get_next_version(video_path: str, output_dir: str) -> int:
    video_name = _sanitize_video_name(video_path)
    history = _history_dir(video_name, output_dir)
    if not os.path.isdir(history):
        return 1
    max_v = 0
    for fname in os.listdir(history):
        m = re.match(r"v(\d+)\.json$", fname)
        if m:
            v = int(m.group(1))
            if v > max_v:
                max_v = v
    return max_v + 1


def save_history(output_dict: dict[str, Any], video_path: str, output_dir: str) -> int:
    video_name = _sanitize_video_name(video_path)
    version = get_next_version(video_path, output_dir)
    hdir = _history_dir(video_name, output_dir)
    os.makedirs(hdir, exist_ok=True)

    entry = dict(output_dict)
    meta = dict(entry.get("_meta") or {})
    meta["history_version"] = version
    meta["template_version"] = get_template_version()
    meta["history_saved_at"] = datetime.now(UTC).isoformat()
    entry["_meta"] = meta

    vfile = _version_file(video_name, output_dir, version)
    with open(vfile, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2)

    return version


def load_history(video_path: str, output_dir: str, version: int) -> dict[str, Any] | None:
    video_name = _sanitize_video_name(video_path)
    vfile = _version_file(video_name, output_dir, version)
    if not os.path.isfile(vfile):
        return None
    with open(vfile, encoding="utf-8") as f:
        return json.load(f)


def list_versions(video_path: str, output_dir: str) -> list[dict[str, Any]]:
    video_name = _sanitize_video_name(video_path)
    hdir = _history_dir(video_name, output_dir)
    if not os.path.isdir(hdir):
        return []

    entries = []
    for fname in sorted(os.listdir(hdir)):
        m = re.match(r"v(\d+)\.json$", fname)
        if m:
            v = int(m.group(1))
            vfile = os.path.join(hdir, fname)
            try:
                with open(vfile, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
            meta = data.get("_meta") or {}
            entries.append({
                "version": v,
                "template_version": meta.get("template_version", "?"),
                "saved_at": meta.get("history_saved_at", "?"),
                "fallback_active": meta.get("fallback_active", False),
                "shots": len((data.get("blueprint") or {}).get("chronological_shots") or []),
                "models": list((data.get("prompts") or {}).keys()),
            })
    return entries
