from __future__ import annotations

import json
import os
import shutil
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
from utils.error_codes import VRError, VRErrorCode, resolve_error_code
from utils.fallback import FallbackMode, build_fallback_blueprint, compile_fallback_prompts, log_fallback_usage
from utils.logger import debug, error, info, log_pipeline_step, set_log_level, warn
from utils.metrics import PipelineMetrics
from utils.retry import RETRY_CONFIG, _is_retriable_error, extract_status_code, with_retry
from utils.validation import sanitize_blueprint, validate_blueprint
from utils.video_type import detect_video_type, get_video_type_label


def _cleanup_temp_dir(results: dict[str, Any]) -> None:
    temp_dir = results.get("steps", {}).get("ingest", {}).get("output_dir")
    if temp_dir and os.path.isdir(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            debug("cleanup", f"Removed temp directory: {temp_dir}")
        except Exception as e:
            warn("cleanup", f"Failed to remove temp directory {temp_dir}: {e}")


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
    metrics = PipelineMetrics(options)
    fallback = FallbackMode()

    _emit_progress(
        on_progress,
        "pipeline_start",
        message="Starting VideoReverse pipeline",
        video_path=options.get("video_path"),
        environment=detect_environment(),
    )
    _emit_progress(on_progress, "step", step="resolve", status="running", message="Resolving video path")

    normalized = normalize_for_env(options.get("video_path"), options.get("wsl_mode"))
    video_type = options.get("video_type")

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
        metrics.start_step("ingest")
        _emit_progress(
            on_progress,
            "step",
            step="ingest",
            status="running",
            message="Extracting metadata, frames, and audio with ffmpeg",
        )
        print("\n── Ingestion & Sampling ──\n", flush=True)

        def _on_ingest_progress(phase: str, message: str) -> None:
            _emit_progress(
                on_progress,
                "step",
                step="ingest",
                status="running",
                message=message,
                phase=phase,
            )

        def _on_ingest_retry(attempt: int, delay_ms: int, err_msg: str) -> None:
            metrics.retries += 1
            _emit_progress(
                on_progress,
                "retry",
                step="ingest",
                attempt=attempt,
                max_retries=options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                delay_ms=delay_ms,
                message=f"Ingest failed - retrying in {delay_ms / 1000:.1f}s ({attempt}/{options.get('max_retries', RETRY_CONFIG['maxRetries'])})",
                detail=err_msg,
            )

        try:
            step1_data = await with_retry(
                lambda: ingest_video(normalized, options=options, on_progress=_on_ingest_progress),
                {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                on_retry=_on_ingest_retry,
            )
            results["steps"]["ingest"] = step1_data
            metrics.end_step("ingest")

            detected_type = detect_video_type(step1_data.get("video_metadata"), step1_data.get("extraction"))
            metrics.video_type = detected_type
            meta = step1_data.get("video_metadata") or {}
            metrics.video_duration = meta.get("duration_seconds")
            info("video-type", f"Detected: {detected_type}")

            if options.get("video_type") and options["video_type"] != detected_type:
                warn("video-type", f"Override: {options['video_type']} (detected: {detected_type})")
        except Exception as err:
            err_msg = f"Ingestion failed: {err}"
            metrics.end_step("ingest")
            metrics.record_error("ingest", err_msg)
            results["errors"].append({"step": "ingest", "error": err_msg})
            error("ingest", err_msg)
            metrics.success = False
            metrics.write()
            if not isinstance(err, VRError):
                code = resolve_error_code(err) or VRErrorCode.INTERNAL_ERROR
                raise VRError(code, detail=str(err), cause=err) from err
            raise

        log_pipeline_step("ingest", metrics.timing_ms.get("ingest_ms", 0), True)
        _emit_progress(
            on_progress,
            "step",
            step="ingest",
            status="done",
            message="Ingestion complete",
            duration_ms=metrics.timing_ms.get("ingest_ms", 0),
        )

        blueprint = None
        metrics.start_step("synthesize")
        _emit_progress(
            on_progress,
            "step",
            step="synthesize",
            status="running",
            message="Analyzing video with Gemini AI",
        )
        print("\n── Blueprint Synthesis ──\n", flush=True)

        def _on_synth_retry(attempt: int, delay_ms: int, err_msg: str) -> None:
            metrics.retries += 1
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
            metrics.end_step("synthesize")
        except Exception as err:
            metrics.end_step("synthesize")

            status = getattr(err, "status_code", None) or extract_status_code(str(err))
            use_fallback = options.get("force") or options.get("use_fallback", True)
            is_transient = _is_retriable_error(str(err), status)

            if use_fallback and is_transient:
                fallback.activate(f"Gemini synthesis failed: {err}")
                metrics.fallback_active = True
                metrics.fallback_reason = str(err)
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
                code = resolve_error_code(err) or VRErrorCode.GEMINI_SYNTHESIS_FAILED
                raise VRError(code, detail=str(err), cause=err) from err

        log_pipeline_step("synthesis", metrics.timing_ms.get("synthesize_ms", 0), not fallback.is_active())
        _emit_progress(
            on_progress,
            "step",
            step="synthesize",
            status="done",
            message="Blueprint ready" + (" (fallback mode)" if fallback.is_active() else ""),
            duration_ms=metrics.timing_ms.get("synthesize_ms", 0),
            fallback=fallback.is_active(),
        )

        prompts = None
        metrics.start_step("compile")
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
            metrics.end_step("compile")
        except Exception as err:
            metrics.end_step("compile")
            error("compile", f"Prompt compilation failed: {err}")

            if fallback.is_active():
                prompts = compile_fallback_prompts(blueprint, results["steps"]["ingest"])
                results["steps"]["compile"] = prompts
            else:
                raise VRError(VRErrorCode.COMPILATION_FAILED, detail=str(err), cause=err) from err

        log_pipeline_step("compile", metrics.timing_ms.get("compile_ms", 0), True)
        _emit_progress(
            on_progress,
            "step",
            step="compile",
            status="done",
            message=f"Compiled prompts for {len(prompts or {})} model(s)",
            duration_ms=metrics.timing_ms.get("compile_ms", 0),
            model_count=len(prompts or {}),
        )

        shots_list = blueprint.get("chronological_shots") or [] if blueprint else []
        metrics.shots_detected = len(shots_list)
        metrics.models_compiled = len(prompts or {})
        metrics.fallback_active = fallback.is_active()
        metrics.fallback_reason = fallback.get_reason()

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

        metrics.timing_ms["total_ms"] = round(metrics.elapsed_seconds * 1000, 1)

        if options.get("dry_run"):
            metrics.write()
            _emit_progress(on_progress, "step", step="export", status="done", message="Dry run — results not saved to disk")
            _emit_progress(
                on_progress,
                "pipeline_complete",
                message="Pipeline finished (dry run)",
                timing=metrics.timing_ms,
                shot_count=metrics.shots_detected,
                model_count=metrics.models_compiled,
                fallback=fallback.is_active(),
                output=results["output"],
            )
            is_quiet = options.get("log_level") == "quiet"
            if not is_quiet:
                print("\n" + "═" * 60, flush=True)
                print("  DRY RUN — No files saved", flush=True)
                print("═" * 60, flush=True)
                print(json.dumps(results["output"], indent=2), flush=True)
            _cleanup_temp_dir(results)
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

        metrics.write()

        print("\n" + "═" * 60, flush=True)
        print("  Pipeline Complete", flush=True)
        print("═" * 60, flush=True)
        total_s = metrics.timing_ms.get("total_ms", 0) / 1000
        print(f"  Duration:  {total_s:.1f}s", flush=True)
        print(f"  Shots:     {metrics.shots_detected}", flush=True)
        print(f"  Models:    {metrics.models_compiled}", flush=True)
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
            timing=metrics.timing_ms,
            shot_count=metrics.shots_detected,
            model_count=metrics.models_compiled,
            fallback=fallback.is_active(),
            output=results["output"],
            files=saved_files,
        )

        _cleanup_temp_dir(results)
        return results["output"]

    except Exception as err:
        metrics.success = False
        metrics.timing_ms["total_ms"] = round(metrics.elapsed_seconds * 1000, 1)
        metrics.record_error("pipeline", str(err))
        metrics.write()

        error("pipeline", f"Pipeline failed after {(metrics.timing_ms.get('total_ms', 0) / 1000):.1f}s")
        error("pipeline", f"Error: {err}")

        if not isinstance(err, VRError):
            code = resolve_error_code(err) or VRErrorCode.INTERNAL_ERROR
            err = VRError(code, detail=str(err), cause=err)

        _emit_progress(
            on_progress,
            "pipeline_error",
            message=err.to_dict(),
            timing=results.get("timing"),
            errors=results.get("errors"),
        )

        _cleanup_temp_dir(results)
        raise
