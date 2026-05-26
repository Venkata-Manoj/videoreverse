from __future__ import annotations

import json
import os
import shutil
import time
from datetime import UTC, datetime
from collections.abc import Callable
from typing import Any

ProgressCallback = Callable[[str, dict[str, Any]], None]

from src.compile import compile_prompts, get_template_version
from src.export import format_text
from src.ingest import ingest_video
from src.path_resolver import normalize_for_env
from src.synthesize import build_blueprint
from utils.cli import detect_environment
from utils.error_codes import VRError, VRErrorCode, resolve_error_code
from utils.logger import debug, error, info, log_pipeline_step, warn
from utils.retry import RETRY_CONFIG, extract_status_code, with_retry
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


def _on_retry(
    step_name: str,
    on_progress: ProgressCallback | None,
    attempt: int,
    delay_ms: int,
    err_msg: str,
    max_retries: int,
) -> None:
    _emit_progress(
        on_progress,
        "retry",
        step=step_name,
        attempt=attempt,
        max_retries=max_retries,
        delay_ms=delay_ms,
        message=f"{step_name} failed — retrying in {delay_ms / 1000:.1f}s ({attempt}/{max_retries})",
        detail=err_msg,
    )


async def run_pipeline(
    options: dict[str, Any],
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    _timing: dict[str, float] = {}
    _t_start = time.monotonic()

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

    print("=" * 60, flush=True)
    print("  VideoReverse — Universal Video-to-Prompt", flush=True)
    print("=" * 60, flush=True)
    print(f"  Environment: {detect_environment()}", flush=True)
    print(f"  Video Type: {get_video_type_label(video_type) or 'auto-detect'}", flush=True)
    print("=" * 60 + "\n", flush=True)

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
        _t_step = time.monotonic()
        _emit_progress(
            on_progress,
            "step",
            step="ingest",
            status="running",
            message="Extracting metadata, frames, and audio with ffmpeg",
        )
        print("\n-- Ingestion & Sampling --\n", flush=True)

        try:
            step1_data = await with_retry(
                lambda: ingest_video(normalized, options=options, on_progress=None),
                {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                on_retry=lambda a, d, m: _on_retry(
                    "ingest", on_progress, a, d, m,
                    options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                ),
            )
            results["steps"]["ingest"] = step1_data
            _timing["ingest_ms"] = round((time.monotonic() - _t_step) * 1000, 1)

            detected_type = detect_video_type(step1_data.get("video_metadata"), step1_data.get("extraction"))
            meta = step1_data.get("video_metadata") or {}
            info("video-type", f"Detected: {detected_type}")

            if options.get("video_type") and options["video_type"] != detected_type:
                warn("video-type", f"Override: {options['video_type']} (detected: {detected_type})")
        except Exception as err:
            err_msg = f"Ingestion failed: {err}"
            results["errors"].append({"step": "ingest", "error": err_msg})
            error("ingest", err_msg)
            if not isinstance(err, VRError):
                code = resolve_error_code(err) or VRErrorCode.INTERNAL_ERROR
                raise VRError(code, detail=str(err), cause=err) from err
            raise

        log_pipeline_step("ingest", _timing.get("ingest_ms", 0), True)
        _emit_progress(
            on_progress,
            "step",
            step="ingest",
            status="done",
            message="Ingestion complete",
            duration_ms=_timing.get("ingest_ms", 0),
        )

        blueprint = None
        _t_step = time.monotonic()
        _emit_progress(
            on_progress,
            "step",
            step="synthesize",
            status="running",
            message="Analyzing video with Gemini AI",
        )
        print("\n-- Blueprint Synthesis --\n", flush=True)

        try:
            blueprint = await with_retry(
                lambda: build_blueprint(normalized, results["steps"]["ingest"], options),
                {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                on_retry=lambda a, d, m: _on_retry(
                    "synthesize", on_progress, a, d, m,
                    options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                ),
            )

            try:
                validate_blueprint(blueprint)
                debug("validation", "Blueprint validation passed")
            except Exception as validation_err:
                warn("validation", f"Invalid blueprint: {validation_err}")
                info("validation", "Attempting to sanitize...")
                blueprint = sanitize_blueprint(blueprint)

            results["steps"]["synthesize"] = blueprint
            _timing["synthesize_ms"] = round((time.monotonic() - _t_step) * 1000, 1)
        except Exception as err:
            _timing["synthesize_ms"] = round((time.monotonic() - _t_step) * 1000, 1)
            code = resolve_error_code(err) or VRErrorCode.GEMINI_SYNTHESIS_FAILED
            raise VRError(code, detail=str(err), cause=err) from err

        log_pipeline_step("synthesis", _timing.get("synthesize_ms", 0), True)
        _emit_progress(
            on_progress,
            "step",
            step="synthesize",
            status="done",
            message="Blueprint ready",
            duration_ms=_timing.get("synthesize_ms", 0),
        )

        prompts = None
        _t_step = time.monotonic()
        _emit_progress(
            on_progress,
            "step",
            step="compile",
            status="running",
            message="Generating model-specific prompts",
        )
        print("\n-- Prompt Compilation --\n", flush=True)

        try:
            prompts = compile_prompts(
                blueprint, results["steps"]["ingest"].get("video_metadata", {}), options.get("models")
            )
            results["steps"]["compile"] = prompts
            _timing["compile_ms"] = round((time.monotonic() - _t_step) * 1000, 1)
        except Exception as err:
            _timing["compile_ms"] = round((time.monotonic() - _t_step) * 1000, 1)
            error("compile", f"Prompt compilation failed: {err}")
            raise VRError(VRErrorCode.COMPILATION_FAILED, detail=str(err), cause=err) from err

        log_pipeline_step("compile", _timing.get("compile_ms", 0), True)
        _emit_progress(
            on_progress,
            "step",
            step="compile",
            status="done",
            message=f"Compiled prompts for {len(prompts or {})} model(s)",
            duration_ms=_timing.get("compile_ms", 0),
            model_count=len(prompts or {}),
        )

        shots_list = blueprint.get("chronological_shots") or [] if blueprint else []
        _shots_detected = len(shots_list)
        _models_compiled = len(prompts or {})

        results["output"] = {
            "video_metadata": results["steps"]["ingest"].get("video_metadata", {}),
            "blueprint": blueprint,
            "prompts": prompts,
            "_meta": {
                "video_type": video_type,
                "fallback_active": False,
                "template_version": get_template_version(),
            },
        }

        _timing["total_ms"] = round((time.monotonic() - _t_start) * 1000, 1)

        if options.get("dry_run"):
            _emit_progress(
                on_progress, "step", step="export", status="done",
                message="Dry run -- results not saved to disk",
            )
            _emit_progress(
                on_progress,
                "pipeline_complete",
                message="Pipeline finished (dry run)",
                timing=_timing,
                shot_count=_shots_detected,
                model_count=_models_compiled,
                output=results["output"],
            )
            is_quiet = options.get("log_level") == "quiet"
            if not is_quiet:
                print("\n" + "=" * 60, flush=True)
                print("  DRY RUN -- No files saved", flush=True)
                print("=" * 60, flush=True)
                print(json.dumps(results["output"], indent=2), flush=True)
            _cleanup_temp_dir(results)
            return results["output"]

        _emit_progress(
            on_progress, "step", step="export", status="running",
            message="Saving JSON and text outputs",
        )
        output_dir = os.path.abspath(options.get("output_dir", "output_blueprints"))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        filename = results["steps"]["ingest"]["video_metadata"]["filename"]
        filename = os.path.splitext(filename)[0]
        timestamp = datetime.now(UTC).isoformat().replace(":", "-").replace(".", "-")
        json_file = os.path.join(output_dir, f"{filename}_{timestamp}.json")

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(results["output"], f, indent=2)
        print(f"\nJSON: {json_file}", flush=True)

        if options.get("format") in ("txt", "both"):
            text_file = os.path.join(output_dir, f"{filename}_{timestamp}.txt")
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(format_text(results["output"]))
            print(f"Text: {text_file}", flush=True)

        print("\n" + "=" * 60, flush=True)
        print("  Pipeline Complete", flush=True)
        print("=" * 60, flush=True)
        total_s = _timing.get("total_ms", 0) / 1000
        print(f"  Duration:  {total_s:.1f}s", flush=True)
        print(f"  Shots:     {_shots_detected}", flush=True)
        print(f"  Models:    {_models_compiled}", flush=True)
        print("=" * 60 + "\n", flush=True)

        saved_files = {"json": json_file}
        if options.get("format") in ("txt", "both"):
            saved_files["txt"] = text_file

        _emit_progress(
            on_progress,
            "step",
            step="export",
            status="done",
            message="Results saved",
            files=saved_files,
        )
        _emit_progress(
            on_progress,
            "pipeline_complete",
            message="Pipeline finished successfully",
            timing=_timing,
            shot_count=_shots_detected,
            model_count=_models_compiled,
            output=results["output"],
            files=saved_files,
        )

        _cleanup_temp_dir(results)
        return results["output"]

    except Exception as err:
        _timing["total_ms"] = round((time.monotonic() - _t_start) * 1000, 1)
        error("pipeline", f"Pipeline failed after {(_timing.get('total_ms', 0) / 1000):.1f}s")
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
