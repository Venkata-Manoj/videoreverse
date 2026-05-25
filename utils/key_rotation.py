from __future__ import annotations

import os
import re
import time
from typing import Any

from src.path_resolver import get_root


def load_api_keys_from_env() -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()

    env_path = os.path.join(get_root(), ".env")
    env_vars: dict[str, str] = {}

    if os.path.exists(env_path):
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    trimmed = line.strip()
                    if not trimmed or trimmed.startswith("#"):
                        continue
                    eq = trimmed.find("=")
                    if eq == -1:
                        continue
                    key = trimmed[:eq].strip()
                    val = trimmed[eq + 1 :].strip()
                    env_vars[key] = val
        except Exception:
            pass

    # Collect from environment (env vars take precedence over .env)
    env_vars.update(os.environ)

    # GEMINI_API_KEY
    primary = env_vars.get("GEMINI_API_KEY")
    if primary and primary not in seen:
        keys.append(primary)
        seen.add(primary)

    # GEMINI_API_KEY_1, GEMINI_API_KEY_2, ...
    for key, val in sorted(env_vars.items(), key=lambda x: _key_sort_key(x[0])):
        m = re.match(r"^GEMINI_API_KEY_(\d+)$", key)
        if m and val and val not in seen:
            keys.append(val)
            seen.add(val)

    return keys


def _key_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"^GEMINI_API_KEY_(\d+)$", name)
    if m:
        return (1, int(m.group(1)))
    return (0, 0)


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return key[:4] + "****"
    return key[:6] + "****" + key[-4:]


class ApiKeyManager:
    def __init__(self, keys: list[str] | None = None) -> None:
        self.keys = keys or load_api_keys_from_env()
        if not self.keys:
            raise RuntimeError(
                "No Gemini API keys found. Set GEMINI_API_KEY in .env or environment."
            )
        self._current_idx = 0
        self._cached_client: Any = None
        self._usage: list[dict[str, Any]] = [
            {"key": mask_key(k), "calls": 0, "errors": 0, "last_error": None, "last_used": None}
            for k in self.keys
        ]

    @property
    def current_key(self) -> str:
        return self.keys[self._current_idx]

    @property
    def current_key_masked(self) -> str:
        return mask_key(self.current_key)

    @property
    def key_count(self) -> int:
        return len(self.keys)

    def get_client(self):
        from google import genai

        if self._cached_client is None:
            self._cached_client = genai.Client(api_key=self.current_key)
        self._usage[self._current_idx]["last_used"] = time.time()
        self._usage[self._current_idx]["calls"] += 1
        return self._cached_client

    def rotate(self) -> str:
        self._cached_client = None
        old_idx = self._current_idx
        self._current_idx = (self._current_idx + 1) % len(self.keys)
        if self._current_idx == old_idx:
            return ""
        msg = f"  ↻ Rotated to API key {self._current_idx + 1}/{len(self.keys)}: {mask_key(self.current_key)}"
        print(msg, flush=True)
        return mask_key(self.current_key)

    def is_rate_limit_error(self, error: Exception) -> bool:
        msg = str(error).lower()
        status = getattr(error, "status_code", None) or getattr(error, "code", None)
        if status is not None:
            try:
                if int(status) == 429:
                    return True
            except (ValueError, TypeError):
                pass
        patterns = [
            "429",
            "rate limit",
            "quota exceeded",
            "too many requests",
            "resource exhausted",
            "insufficient tokens",
        ]
        return any(p in msg for p in patterns)

    def report_error(self, error: Exception) -> bool:
        self._usage[self._current_idx]["errors"] += 1
        self._usage[self._current_idx]["last_error"] = str(error)[:200]

        if self.is_rate_limit_error(error):
            print(f"  ⚠️ Key {self._current_idx + 1}/{len(self.keys)} hit rate limit — rotating...", flush=True)
            rotated = self.rotate()
            return bool(rotated)
        return False

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_keys": len(self.keys),
            "active_key_index": self._current_idx,
            "active_key": self.current_key_masked,
            "keys": list(self._usage),
        }


_manager: ApiKeyManager | None = None


def get_key_manager() -> ApiKeyManager:
    global _manager
    if _manager is None:
        _manager = ApiKeyManager()
    return _manager


def reset_key_manager(keys: list[str] | None = None) -> ApiKeyManager:
    global _manager
    _manager = ApiKeyManager(keys)
    return _manager
