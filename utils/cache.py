from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
CACHE_EXPIRY_MS = 24 * 60 * 60 * 1000  # 24 hours
SCHEMA_VERSION = "1.0.0"


def ensure_cache_dir() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def hash_video_file(video_path: str, byte_limit: int = 64 * 1024) -> str:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    stat = os.stat(video_path)
    read_size = min(stat.st_size, byte_limit)

    h = hashlib.sha256()
    with open(video_path, "rb") as f:
        buffer = f.read(read_size)
    h.update(buffer)
    h.update(f"|{stat.st_size}|{stat.st_mtime}".encode())

    return h.hexdigest()


def get_cache_key(video_path: str, options: dict[str, Any] | None = None) -> str:
    if options is None:
        options = {}
    video_hash = hash_video_file(video_path)
    prefix = video_hash[:16]
    schema_version = options.get("schema_version", SCHEMA_VERSION)
    sample_mode = options.get("sample_mode", "full")
    max_duration = options.get("max_duration")

    return f"blueprint_{prefix}_{schema_version}_{sample_mode}_{max_duration or 'full'}"


def get_cache_info(video_path: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    if options is None:
        options = {}
    ensure_cache_dir()
    key = get_cache_key(video_path, options)
    cache_file = _CACHE_DIR / f"{key}.json"

    if not cache_file.exists():
        return {"hit": False, "key": key, "file": str(cache_file)}

    try:
        with open(cache_file, encoding="utf-8") as f:
            cached = json.load(f)
        age = time.time() * 1000 - cached["timestamp"]
        age_minutes = round(age / 60000)

        if age > CACHE_EXPIRY_MS:
            return {"hit": False, "key": key, "file": str(cache_file), "expired": True, "age_minutes": age_minutes}

        return {
            "hit": True,
            "key": key,
            "file": str(cache_file),
            "age_minutes": age_minutes,
            "expires_in_minutes": round((CACHE_EXPIRY_MS - age) / 60000),
            "video_hash": cached.get("video_hash"),
            "video_size": cached.get("video_size"),
        }
    except Exception:
        return {"hit": False, "key": key, "file": str(cache_file), "corrupted": True}


def get_cached(key: str, cache_type: str = "blueprint") -> Any | None:
    ensure_cache_dir()
    cache_file = _CACHE_DIR / f"{cache_type}_{key}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, encoding="utf-8") as f:
            cached = json.load(f)
        age = time.time() * 1000 - cached["timestamp"]

        if age > CACHE_EXPIRY_MS:
            os.unlink(cache_file)
            return None

        return cached["data"]
    except Exception:
        return None


def get_cached_by_path(video_path: str, options: dict[str, Any] | None = None) -> Any | None:
    if options is None:
        options = {}
    ensure_cache_dir()
    info = get_cache_info(video_path, options)

    if not info["hit"]:
        return None

    try:
        with open(info["file"], encoding="utf-8") as f:
            cached = json.load(f)
        return cached["data"]
    except Exception:
        return None


def set_cache(
    video_path: str,
    data: Any,
    options: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    if options is None:
        options = {}
    ensure_cache_dir()
    key = get_cache_key(video_path, options)
    cache_file = _CACHE_DIR / f"{key}.json"

    try:
        stat = os.stat(video_path)
        video_hash = hash_video_file(video_path)

        cache_data = {
            "timestamp": time.time() * 1000,
            "video_hash": video_hash,
            "video_size": stat.st_size,
            "video_path": video_path,
            "schema_version": options.get("schema_version", SCHEMA_VERSION),
            "sample_mode": options.get("sample_mode", "full"),
            "max_duration": options.get("max_duration"),
            "data": data,
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)

        return {"key": key, "file": str(cache_file)}
    except Exception as e:
        print(f"Cache write failed: {e}", flush=True)
        return None


def clear_cache(cache_type: str | None = None) -> None:
    ensure_cache_dir()

    for file in _CACHE_DIR.iterdir():
        if cache_type:
            if file.name.startswith(f"{cache_type}_"):
                os.unlink(file)
        else:
            os.unlink(file)


def get_cache_stats() -> dict[str, Any]:
    ensure_cache_dir()

    stats: dict[str, Any] = {
        "total": 0,
        "total_size_bytes": 0,
        "byType": {},
        "entries": [],
    }

    for file in _CACHE_DIR.iterdir():
        stat = file.stat()
        stats["total"] += 1
        stats["total_size_bytes"] += stat.st_size

        type_name = file.name.split("_")[0]
        stats["byType"][type_name] = stats["byType"].get(type_name, 0) + 1

        try:
            with open(file, encoding="utf-8") as f:
                cached = json.load(f)
            age = time.time() * 1000 - cached["timestamp"]
            stats["entries"].append(
                {
                    "file": file.name,
                    "age_minutes": round(age / 60000),
                    "expired": age > CACHE_EXPIRY_MS,
                    "video_hash": cached.get("video_hash", "")[:16] if cached.get("video_hash") else None,
                    "video_size": cached.get("video_size"),
                }
            )
        except Exception:
            stats["entries"].append({"file": file.name, "corrupted": True})

    return stats
