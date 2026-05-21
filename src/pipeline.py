from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime, timezone
from collections.abc import Callable
from typing import Any

ProgressCallback = Callable[[str, dict[str, Any]], None]

from src.compile import compile_prompts
from src.export import format_text
from src.ingest import ingest_video
from src.path_resolver import normalize_for_env
from src.synthesize import build_blueprint
from utils.cli import detect_environment
from utils.fallback import FallbackMode, build_fallback_blueprint, compile_fallback_prompts, log_fallback_usage
from utils.logger import debug, error, info, log_pipeline_step, set_log_level, warn
from utils.retry import RETRY_CONFIG, _is_retriable_error, extract_status_code, with_retry
from utils.validation import sanitize_blueprint, validate_blueprint
from utils.video_type import detect_video_type, get_video_type_label


def _normalize_path(target: str | Any, wsl_mode: str | None = None) -> str | Any:
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

    env = wsl_mode or detect_environment()
    if env == "win":
        return os.path.abspath(target)

    is_windows_path = bool(re.match(r"^[a-zA-Z]:[\\/]", target))
    if is_windows_path:
        drive = target[0].lower()
        posix_path = target[2:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{posix_path}"

    if re.match(r"^/mnt/[a-z]/", target, re.IGNORECASE):
        return target
    return os.path.abspath(target)


def _emit_progress(
    callback: ProgressCallback | None,
    event: str,
    *,
    step: str | None = None,
    status: str | None = None,
    message: str | None = None,
    **extra: Any,
) -> None:
    if not callback:
        return
    payload: dict[str, Any] = {}
    if step is not None:
        payload["step"] = step
    if status is not None:
        payload["status"] = status
    if message is not None:
        payload["message"] = message
    payload.update(extra)
    callback(event, payload)


async def run_pipeline(
    options: dict[str, Any],
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    start_time = time.time() * 1000
    fallback = FallbackMode()

    _emit_progress(
        on_progress,
        "pipeline_start",
        message="Starting VideoReverse pipeline",
        video_path=options.get("video_path"),
        environment=detect_environment(),
    )
    _emit_progress(on_progress, "step", step="resolve", status="running", message="Resolving video path")

    normalized = _normalize_path(options.get("video_path"), options.get("wsl_mode"))
    video_type = options.get("video_type") or detect_video_type(None, None)

    _emit_progress(
        on_progress,
        "step",
        step="resolve",
        status="done",
        message="Video path ready",
        resolved_path=normalized if isinstance(normalized, str) else str(normalized),
        video_type=video_type,
    )

    print("═" * 60, flush=True)
    print("  VideoReverse — Universal Video-to-Prompt", flush=True)
    print("═" * 60, flush=True)
    print(f"  Environment: {detect_environment()}", flush=True)
    print(f"  Video Type: {get_video_type_label(video_type) or 'auto-detect'}", flush=True)
    print("═" * 60 + "\n", flush=True)

    results = {
        "input": {
            "original": options.get("video_path"),
            "resolved": normalized,
            "timestamp": datetime.now(UTC).isoformat(),
            "video_type": video_type,
            "options": options,
        },
        "steps": {},
        "output": None,
        "timing": {},
        "errors": [],
    }

    try:
        ingest_start = time.time() * 1000
        _emit_progress(
            on_progress,
            "step",
            step="ingest",
            status="running",
            message="Extracting metadata, frames, and audio with ffmpeg",
        )
        print("\n── Ingestion & Sampling ──\n", flush=True)

        try:
            step1_data = await with_retry(
                lambda: ingest_video(normalized), {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])}
            )
            results["steps"]["ingest"] = step1_data
            results["timing"]["ingest_ms"] = time.time() * 1000 - ingest_start

            detected_type = detect_video_type(step1_data.get("video_metadata"), step1_data.get("extraction"))
            info("video-type", f"Detected: {detected_type}")

            if options.get("video_type") and options["video_type"] != detected_type:
                warn("video-type", f"Override: {options['video_type']} (detected: {detected_type})")
        except Exception as err:
            err_msg = f"Ingestion failed: {err}"
            results["errors"].append({"step": "ingest", "error": err_msg})
            error("ingest", err_msg)
            raise

        log_pipeline_step("ingest", results["timing"]["ingest_ms"], True)
        _emit_progress(
            on_progress,
            "step",
            step="ingest",
            status="done",
            message="Ingestion complete",
            duration_ms=results["timing"]["ingest_ms"],
        )

        blueprint = None
        synth_start = time.time() * 1000
        _emit_progress(
            on_progress,
            "step",
            step="synthesize",
            status="running",
            message="Analyzing video with Gemini AI",
        )
        print("\n── Blueprint Synthesis ──\n", flush=True)

        def _on_synth_retry(attempt: int, delay_ms: int, err_msg: str) -> None:
            _emit_progress(
                on_progress,
                "retry",
                step="synthesize",
                attempt=attempt,
                max_retries=options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                delay_ms=delay_ms,
                message=f"Gemini busy — retrying in {delay_ms / 1000:.1f}s ({attempt}/{options.get('max_retries', RETRY_CONFIG['maxRetries'])})",
                detail=err_msg,
            )

        try:
            blueprint = await with_retry(
                lambda: build_blueprint(normalized, results["steps"]["ingest"], options),
                {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                on_retry=_on_synth_retry,
            )

            try:
                validate_blueprint(blueprint)
                debug("validation", "Blueprint validation passed")
            except Exception as validation_err:
                warn("validation", f"Invalid blueprint: {validation_err}")
                info("validation", "Attempting to sanitize...")
                blueprint = sanitize_blueprint(blueprint)

            results["steps"]["synthesize"] = blueprint
            results["timing"]["synthesize_ms"] = time.time() * 1000 - synth_start
        except Exception as err:
            results["timing"]["synthesize_ms"] = time.time() * 1000 - synth_start

            status = getattr(err, "status_code", None) or extract_status_code(str(err))
            use_fallback = options.get("force") or options.get("use_fallback", True)
            is_transient = _is_retriable_error(str(err), status)

            if use_fallback and is_transient:
                fallback.activate(f"Gemini synthesis failed: {err}")
                log_fallback_usage(fallback, "synthesis", err)
                _emit_progress(
                    on_progress,
                    "fallback",
                    step="synthesize",
                    message="Gemini unavailable — using metadata-based fallback blueprint",
                    detail=str(err),
                )

                blueprint = build_fallback_blueprint(results["steps"]["ingest"])
                results["steps"]["synthesize"] = blueprint
                results["steps"]["synthesize"]["_fallback"] = True
            else:
                raise

        log_pipeline_step("synthesis", results["timing"]["synthesize_ms"], not fallback.is_active())
        _emit_progress(
            on_progress,
            "step",
            step="synthesize",
            status="done",
            message="Blueprint ready" + (" (fallback mode)" if fallback.is_active() else ""),
            duration_ms=results["timing"]["synthesize_ms"],
            fallback=fallback.is_active(),
        )

        prompts = None
        compile_start = time.time() * 1000
        _emit_progress(
            on_progress,
            "step",
            step="compile",
            status="running",
            message="Generating model-specific prompts",
        )
        print("\n── Prompt Compilation ──\n", flush=True)

        try:
            prompts = compile_prompts(
                blueprint, results["steps"]["ingest"].get("video_metadata", {}), options.get("models")
            )

            results["steps"]["compile"] = prompts
            results["timing"]["compile_ms"] = time.time() * 1000 - compile_start
        except Exception as err:
            results["timing"]["compile_ms"] = time.time() * 1000 - compile_start
            error("compile", f"Prompt compilation failed: {err}")

            if fallback.is_active():
                prompts = compile_fallback_prompts(blueprint, results["steps"]["ingest"])
                results["steps"]["compile"] = prompts
            else:
                raise

        log_pipeline_step("compile", results["timing"]["compile_ms"], True)
        _emit_progress(
            on_progress,
            "step",
            step="compile",
            status="done",
            message=f"Compiled prompts for {len(prompts or {})} model(s)",
            duration_ms=results["timing"]["compile_ms"],
            model_count=len(prompts or {}),
        )

        results["output"] = {
            "video_metadata": results["steps"]["ingest"].get("video_metadata", {}),
            "blueprint": blueprint,
            "prompts": prompts,
            "_meta": {
                "video_type": video_type,
                "fallback_active": fallback.is_active(),
                "fallback_reason": fallback.get_reason(),
            },
        }

        results["timing"]["total_ms"] = time.time() * 1000 - start_time

        if options.get("dry_run"):
            _emit_progress(on_progress, "step", step="export", status="done", message="Dry run — results not saved to disk")
            _emit_progress(
                on_progress,
                "pipeline_complete",
                message="Pipeline finished (dry run)",
                timing=results["timing"],
                shot_count=len(blueprint.get("chronological_shots", [])),
                model_count=len(prompts or {}),
                fallback=fallback.is_active(),
                output=results["output"],
            )
            print("\n" + "═" * 60, flush=True)
            print("  DRY RUN — No files saved", flush=True)
            print("═" * 60, flush=True)
            print(json.dumps(results["output"], indent=2), flush=True)
            return results["output"]

        _emit_progress(on_progress, "step", step="export", status="running", message="Saving JSON and text outputs")
        output_dir = os.path.abspath(options.get("output_dir", "output_blueprints"))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        filename = results["steps"]["ingest"]["video_metadata"]["filename"]
        filename = os.path.splitext(filename)[0]
        timestamp = datetime.now(UTC).isoformat().replace(":", "-").replace(".", "-")
        json_file = os.path.join(output_dir, f"{filename}_{timestamp}.json")

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(results["output"], f, indent=2)
        print(f"\n💾 JSON: {json_file}", flush=True)

        if options.get("format") in ("txt", "both"):
            text_file = os.path.join(output_dir, f"{filename}_{timestamp}.txt")
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(format_text(results["output"]))
            print(f"📄 Text: {text_file}", flush=True)

        print("\n" + "═" * 60, flush=True)
        print("  Pipeline Complete", flush=True)
        print("═" * 60, flush=True)
        print(f"  Duration:  {(results['timing']['total_ms'] / 1000):.1f}s", flush=True)
        print(f"  Shots:     {len(blueprint.get('chronological_shots', []))}", flush=True)
        print(f"  Models:    {len(prompts)}", flush=True)
        fallback_status = "YES ⚠️" if fallback.is_active() else "NO"
        print(f"  Fallback:  {fallback_status}", flush=True)

        if fallback.is_active():
            print(f"  Reason:    {fallback.get_reason()}", flush=True)

        print("═" * 60 + "\n", flush=True)

        saved_files = {"json": json_file}
        if options.get("format") in ("txt", "both"):
            saved_files["txt"] = text_file

        _emit_progress(
            on_progress,
            "step",
            step="export",
            status="done",
            message="Results saved",
            duration_ms=0,
            files=saved_files,
        )
        _emit_progress(
            on_progress,
            "pipeline_complete",
            message="Pipeline finished successfully",
            timing=results["timing"],
            shot_count=len(blueprint.get("chronological_shots", [])),
            model_count=len(prompts or {}),
            fallback=fallback.is_active(),
            output=results["output"],
            files=saved_files,
        )

        return results["output"]

    except Exception as err:
        results["timing"]["total_ms"] = time.time() * 1000 - start_time
        results["error"] = str(err)
        results["errors"].append({"step": "pipeline", "error": str(err)})

        error("pipeline", f"Pipeline failed after {(results['timing']['total_ms'] / 1000):.1f}s")
        error("pipeline", f"Error: {err}")

        err_str = str(err)
        if "ffmpeg" in err_str:
            print("\n   Fix: apt install ffmpeg  (or brew install ffmpeg)", flush=True)
        elif "GEMINI_API_KEY" in err_str:
            print("\n   Fix: Add GEMINI_API_KEY to .env file", flush=True)
        elif "not found" in err_str:
            print("\n   Fix: Check the video path is correct and accessible", flush=True)

        _emit_progress(
            on_progress,
            "pipeline_error",
            message=str(err),
            timing=results.get("timing"),
            errors=results.get("errors"),
        )

        raise
