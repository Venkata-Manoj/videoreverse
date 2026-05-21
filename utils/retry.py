from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

RETRY_CONFIG: dict[str, Any] = {
    "maxRetries": 5,
    "baseDelay": 2000,
    "maxDelay": 60000,
    "exponentialBase": 2,
    "jitterFactor": 0.1,
}

_HTTP_STATUS_RE = re.compile(r"\b(429|500|502|503|504)\b")


class RetriableError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.name = "RetriableError"
        self.status_code = status_code
        self.is_retriable = _is_retriable_error(message, status_code)


def extract_status_code(message: str | None) -> int | None:
    if not message:
        return None
    match = _HTTP_STATUS_RE.search(message)
    if match:
        return int(match.group(1))
    return None


def _is_retriable_error(message: str | None, status_code: int | None = None) -> bool:
    if status_code is None and message:
        status_code = extract_status_code(message)

    if status_code is not None:
        return status_code in [429, 500, 502, 503, 504]

    msg = (message or "").lower()
    retriable_patterns = [
        "rate limit",
        "quota exceeded",
        "too many requests",
        "service unavailable",
        "unavailable",
        "high demand",
        "overloaded",
        "internal server error",
        "bad gateway",
        "gateway timeout",
        "timeout",
        "connection reset",
        "network error",
        "econnreset",
        "econnrefused",
        "socket hang up",
    ]
    return any(pattern in msg for pattern in retriable_patterns)


def api_error_from_exception(exc: Exception) -> Exception:
    """Normalize provider errors so retry/fallback logic can classify them."""
    if isinstance(exc, RetriableError):
        return exc

    message = str(exc)
    status_code = (
        getattr(exc, "status_code", None)
        or getattr(exc, "code", None)
        or extract_status_code(message)
    )
    if isinstance(status_code, str) and status_code.isdigit():
        status_code = int(status_code)

    if _is_retriable_error(message, status_code if isinstance(status_code, int) else None):
        return RetriableError(message, status_code=status_code if isinstance(status_code, int) else None)

    return exc


def calculate_delay(attempt: int, config: dict[str, Any] | None = None) -> int:
    if config is None:
        config = RETRY_CONFIG
    exponential_delay = config["baseDelay"] * (config["exponentialBase"] ** (attempt - 1))
    capped_delay = min(exponential_delay, config["maxDelay"])
    jitter = capped_delay * config["jitterFactor"] * random.random()
    return int(capped_delay + jitter)


async def with_retry(
    fn: Callable[[], T | asyncio.Future[T]],
    options: dict[str, Any] | None = None,
    on_retry: Callable[[int, int, str], None] | None = None,
) -> T:
    if options is None:
        options = {}
    config = {**RETRY_CONFIG, **options}
    last_error = None

    for attempt in range(1, config["maxRetries"] + 2):
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as error:
            last_error = api_error_from_exception(error)
            is_retriable = isinstance(last_error, RetriableError) and last_error.is_retriable
            if not is_retriable:
                is_retriable = _is_retriable_error(
                    str(last_error), getattr(last_error, "status_code", None)
                )

            if not is_retriable or attempt > config["maxRetries"]:
                raise last_error from error

            delay = calculate_delay(attempt, config)
            msg = f"Retry {attempt}/{config['maxRetries']} in {(delay / 1000):.1f}s — {last_error}"
            print(f"   ↻ {msg}", flush=True)
            if on_retry:
                on_retry(attempt, delay, str(last_error))
            await asyncio.sleep(delay / 1000)

    raise last_error


async def sleep(ms: int) -> None:
    await asyncio.sleep(ms / 1000)


def parse_retry_args(args: list[str]) -> dict[str, Any]:
    result = {
        "maxRetries": RETRY_CONFIG["maxRetries"],
        "force": False,
    }

    i = 0
    while i < len(args):
        if args[i] in ("--max-retries", "-r"):
            if i + 1 < len(args):
                try:
                    val = int(args[i + 1])
                    if val >= 0:
                        result["maxRetries"] = val
                    i += 1
                except ValueError:
                    pass
        elif args[i] in ("--force", "-f"):
            result["force"] = True
        i += 1

    return result
