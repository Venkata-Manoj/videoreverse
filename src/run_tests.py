import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.path_resolver import get_root
from src.pipeline import run_pipeline

TEST_VIDEOS = [
    {
        "name": "test1.mp4",
        "description": "CGI/Animation",
        "expected_type": "cgi",
        "required": True,
    },
    {
        "name": "test_drone.mp4",
        "description": "Aerial/Drone Footage",
        "expected_type": "drone",
        "required": False,
    },
    {
        "name": "test_anime.mp4",
        "description": "2D Animation/Anime",
        "expected_type": "animation",
        "required": False,
    },
    {
        "name": "test_vlog.mp4",
        "description": "Handheld Multi-cut Vlog",
        "expected_type": "live-action",
        "required": False,
    },
]

PROJECT_ROOT = get_root()
RESULTS_DIR = os.path.join(PROJECT_ROOT, "test_results")
SUMMARY_FILE = os.path.join(RESULTS_DIR, "test_summary.json")


def _ensure_results_dir() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)


def _validate_output(filename: str) -> dict[str, Any]:
    try:
        with open(filename, encoding="utf-8") as f:
            data = json.load(f)

        checks = {
            "has_video_metadata": bool(data.get("video_metadata")),
            "has_blueprint": bool(data.get("blueprint")),
            "has_prompts": bool(data.get("prompts")),
            "has_global_aesthetic": bool(data.get("blueprint", {}).get("global_aesthetic")),
            "has_chronological_shots": isinstance(data.get("blueprint", {}).get("chronological_shots"), list),
            "has_model_outputs": len(data.get("prompts", {})) > 0,
        }

        passed = all(checks.values())
        score = (sum(1 for v in checks.values() if v) / len(checks)) * 100

        return {"passed": passed, "score": score, "checks": checks, "data": data}
    except Exception as error:
        return {
            "passed": False,
            "score": 0,
            "error": str(error),
            "checks": {},
        }


async def _run_pipeline(video_path: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    if options is None:
        options = {}
    opts = {
        "video_path": video_path,
        "output_dir": RESULTS_DIR,
        "format": "both",
        "models": options.get("model"),
        "dry_run": options.get("dry_run", False),
        "verbose": options.get("verbose", False),
        "log_level": "debug" if options.get("verbose") else "info",
        "quiet": False,
        "force": False,
        "max_retries": 3,
        "max_duration": None,
        "sample_mode": "full",
        "video_type": None,
        "no_cache": False,
        "wsl_mode": None,
    }

    try:
        result = await run_pipeline(opts)
        return {"success": True, "result": result}
    except Exception as error:
        return {"success": False, "error": str(error)}


async def run_tests() -> dict[str, Any]:
    print("═" * 60, flush=True)
    print("  VideoReverse — Test Suite", flush=True)
    print("═" * 60 + "\n", flush=True)

    _ensure_results_dir()

    results: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "total": len(TEST_VIDEOS),
        "passed": 0,
        "failed": 0,
        "tests": [],
    }

    for test in TEST_VIDEOS:
        test_name = str(test["name"])
        video_path = os.path.join(PROJECT_ROOT, test_name)
        exists = os.path.exists(video_path)

        print(f"\n┌─ Test: {test['name']}", flush=True)
        print(f"│  Description: {test['description']}", flush=True)
        print(f"│  Expected Type: {test['expected_type']}", flush=True)
        print(f"│  Required: {'YES' if test['required'] else 'NO'}", flush=True)

        if not exists:
            print("│", flush=True)
            print("└─ ⏭️  SKIPPED (file not found)", flush=True)
            results["tests"].append(
                {
                    "name": test["name"],
                    "status": "skipped",
                    "reason": "file not found",
                    "required": test["required"],
                }
            )
            if test["required"]:
                results["failed"] += 1
            continue

        start_time = time.time() * 1000
        result = await _run_pipeline(video_path, {"verbose": False})
        duration = time.time() * 1000 - start_time

        if result["success"]:
            base_name = test_name.replace(".mp4", "")
            output_files = [os.path.join(RESULTS_DIR, f) for f in os.listdir(RESULTS_DIR) if f.startswith(base_name)]

            json_file = next((f for f in output_files if f.endswith(".json")), None)
            txt_file = next((f for f in output_files if f.endswith(".txt")), None)

            validation = None
            if json_file:
                validation = _validate_output(json_file)

            if validation and validation["passed"]:
                print("│", flush=True)
                print(f"└─ ✅ PASSED ({duration / 1000:.1f}s, score: {validation['score']:.0f}%)", flush=True)
                results["passed"] += 1
                results["tests"].append(
                    {
                        "name": test["name"],
                        "status": "passed",
                        "duration_ms": duration,
                        "validation": validation,
                        "output_files": {"json": json_file, "txt": txt_file},
                    }
                )
            else:
                print("│", flush=True)
                score = validation["score"] if validation else 0
                reason = validation.get("error", "validation failed") if validation else "no output"
                print(f"└─ ❌ FAILED (validation score: {score:.0f}%)", flush=True)
                results["failed"] += 1
                results["tests"].append(
                    {
                        "name": test["name"],
                        "status": "failed",
                        "reason": reason,
                        "duration_ms": duration,
                        "validation": validation,
                    }
                )
        else:
            print("│", flush=True)
            print(f"└─ ❌ FAILED (error: {result['error']})", flush=True)
            results["failed"] += 1
            results["tests"].append(
                {
                    "name": test["name"],
                    "status": "failed",
                    "error": result["error"],
                    "duration_ms": duration,
                }
            )

    skipped = sum(1 for t in results["tests"] if t["status"] == "skipped")

    print("\n" + "═" * 60, flush=True)
    print("  Test Summary", flush=True)
    print("═" * 60, flush=True)
    print(f"  Total:  {results['total']}", flush=True)
    print(f"  Passed: {results['passed']} ✅", flush=True)
    print(f"  Failed: {results['failed']} ❌", flush=True)
    print(f"  Skipped: {skipped}", flush=True)
    print("═" * 60 + "\n", flush=True)

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"  Full report: {SUMMARY_FILE}", flush=True)

    return results


def main() -> None:
    results = asyncio.run(run_tests())
    sys.exit(1 if results["failed"] > 0 else 0)


if __name__ == "__main__":
    main()
