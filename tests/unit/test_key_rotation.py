from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

from tests.unit.test_framework import expect, it

import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.key_rotation import (
    ApiKeyManager,
    load_api_keys_from_env,
    mask_key,
    reset_key_manager,
)


def _create_env_file(keys: dict[str, str]) -> str:
    tmp = tempfile.mkstemp(suffix=".env", text=True)
    content = "\n".join(f"{k}={v}" for k, v in keys.items())
    os.write(tmp[0], content.encode())
    os.close(tmp[0])
    return tmp[1]


# =======================
# mask_key
# =======================

def _masks_long_key() -> None:
    result = mask_key("AIzaSyA1b2C3d4E5f6G7h8I9j0KlMnOpQrStUvWxYz")
    expect(result).to_be("AIzaSy****WxYz")

it("masks long API keys", _masks_long_key)


def _masks_short_key() -> None:
    result = mask_key("abc12345")
    expect(result).to_be("abc1****")

it("masks short keys", _masks_short_key)


def _handles_empty_key() -> None:
    result = mask_key("")
    expect(result).to_be("****")

it("handles empty key", _handles_empty_key)


# =======================
# load_api_keys_from_env
# =======================

def _loads_single_key() -> None:
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1"}, clear=True):
        with patch("utils.key_rotation.get_root", return_value=tempfile.gettempdir()):
            keys = load_api_keys_from_env()
            expect("test-key-1" in keys).to_be(True)
            expect(len(keys)).to_be(1)

it("loads single key from env", _loads_single_key)


def _loads_multiple_keys() -> None:
    with patch.dict(
        os.environ,
        {"GEMINI_API_KEY": "primary", "GEMINI_API_KEY_1": "second", "GEMINI_API_KEY_2": "third"},
        clear=True,
    ):
        with patch("utils.key_rotation.get_root", return_value=tempfile.gettempdir()):
            keys = load_api_keys_from_env()
            expect(len(keys)).to_be(3)
            expect(keys[0]).to_be("primary")
            expect(keys[1]).to_be("second")
            expect(keys[2]).to_be("third")

it("loads multiple keys from env", _loads_multiple_keys)


def _deduplicates_keys() -> None:
    with patch.dict(os.environ, {"GEMINI_API_KEY": "same", "GEMINI_API_KEY_1": "same"}, clear=True):
        with patch("utils.key_rotation.get_root", return_value=tempfile.gettempdir()):
            keys = load_api_keys_from_env()
            expect(len(keys)).to_be(1)

it("deduplicates identical keys", _deduplicates_keys)


def _skips_empty_keys() -> None:
    with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GEMINI_API_KEY_1": "valid"}, clear=True):
        with patch("utils.key_rotation.get_root", return_value=tempfile.gettempdir()):
            keys = load_api_keys_from_env()
            expect(len(keys)).to_be(1)
            expect(keys[0]).to_be("valid")

it("skips empty key values", _skips_empty_keys)


def _returns_empty_when_none_found() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with patch("utils.key_rotation.get_root", return_value=tempfile.gettempdir()):
            keys = load_api_keys_from_env()
            expect(keys).to_be([])

it("returns empty list when no keys", _returns_empty_when_none_found)


# =======================
# ApiKeyManager
# =======================

def _uses_first_key_by_default() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    expect(mgr.current_key).to_be("key-a")
    expect(mgr.current_key_masked != "key-a").to_be(True)  # should be masked

it("uses first key by default", _uses_first_key_by_default)


def _rotates_to_next_key() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    mgr.rotate()
    expect(mgr.current_key).to_be("key-b")

it("rotates to next key", _rotates_to_next_key)


def _rotates_back_to_start() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    mgr.rotate()
    mgr.rotate()
    expect(mgr.current_key).to_be("key-a")

it("rotates back to first key", _rotates_back_to_start)


def _tracks_per_key_usage() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    mgr.get_client()
    mgr.get_client()
    expect(mgr.stats["keys"][0]["calls"]).to_be(2)
    expect(mgr.stats["keys"][1]["calls"]).to_be(0)

it("tracks per-key usage", _tracks_per_key_usage)


def _usage_follows_rotation() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    mgr.get_client()
    mgr.rotate()
    mgr.get_client()
    mgr.get_client()
    expect(mgr.stats["keys"][0]["calls"]).to_be(1)
    expect(mgr.stats["keys"][1]["calls"]).to_be(2)

it("usage follows rotation", _usage_follows_rotation)


def _detects_429_rate_limit() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    err = type("FakeError", (Exception,), {"status_code": 429})("rate limit")
    expect(mgr.is_rate_limit_error(err)).to_be(True)

it("detects 429 rate limit errors", _detects_429_rate_limit)


def _detects_rate_limit_by_message() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    err = Exception("Resource exhausted: quota exceeded")
    expect(mgr.is_rate_limit_error(err)).to_be(True)

it("detects rate limit by message", _detects_rate_limit_by_message)


def _report_error_rotates_on_429() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    err = type("Fake429", (Exception,), {"status_code": 429})("rate limit")
    rotated = mgr.report_error(err)
    expect(rotated).to_be(True)
    expect(mgr.current_key).to_be("key-b")

it("report_error rotates on 429", _report_error_rotates_on_429)


def _report_error_does_not_rotate_on_other_errors() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    err = Exception("some other error")
    rotated = mgr.report_error(err)
    expect(rotated).to_be(False)
    expect(mgr.current_key).to_be("key-a")  # unchanged

it("report_error does not rotate on other errors", _report_error_does_not_rotate_on_other_errors)


def _tracks_errors_per_key() -> None:
    mgr = ApiKeyManager(["key-a", "key-b"])
    mgr.report_error(Exception("err1"))
    mgr.report_error(Exception("err2"))
    expect(mgr.stats["keys"][0]["errors"]).to_be(2)
    expect(mgr.stats["keys"][1]["errors"]).to_be(0)

it("tracks errors per key", _tracks_errors_per_key)


def _key_count_property() -> None:
    mgr = ApiKeyManager(["a", "b", "c"])
    expect(mgr.key_count).to_be(3)

it("key_count returns correct count", _key_count_property)


def _reset_key_manager_creates_new() -> None:
    reset_key_manager(["custom-key"])
    from utils.key_rotation import get_key_manager

    mgr = get_key_manager()
    expect(mgr.current_key).to_be("custom-key")

it("reset_key_manager replaces instance", _reset_key_manager_creates_new)


def _get_client_returns_client() -> None:
    mgr = ApiKeyManager(["test-key"])
    with patch("google.genai.Client") as mock_client:
        client = mgr.get_client()
        mock_client.assert_called_once_with(api_key="test-key")
        expect(client).to_be(mock_client.return_value)

it("get_client creates genai.Client", _get_client_returns_client)


def _stats_contains_all_keys() -> None:
    mgr = ApiKeyManager(["a", "b"])
    stats = mgr.stats
    expect(stats["total_keys"]).to_be(2)
    expect(stats["active_key_index"]).to_be(0)
    expect(len(stats["keys"])).to_be(2)

it("stats contains all key info", _stats_contains_all_keys)
