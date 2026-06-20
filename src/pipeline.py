from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from src.compile import compile_prompts, get_template_version
from src.export import format_text
from src.ingest import ingest_video
from src.path_resolver import normalize_for_env
from src.synthesize import build_blueprint
from utils.cli import detect_environment
from utils.error_codes import VRError, VRErrorCode, resolve_error_code
from utils.logger import debug, error, info, log_pipeline_step, warn
from utils.retry import RETRY_CONFIG, extract_status_code, with_retry
from utils.sampler import cleanup_sample, sample_video
from utils.validation import sanitize_blueprint, validate_blueprint
from utils.video_type import detect_video_type, get_video_type_label

ProgressCallback = Callable[[str, dict[str, Any]], None]


def _compress_video(video_path: str, options: dict[str, Any]) -> dict[str, Any] | None:
    if options.get("no_compress"):
        return None

    target_width = options.get("compress_width", 720)
    try:
        temp_dir = tempfile.mkdtemp(prefix="vidrev-compress-")
        ext = os.path.splitext(video_path)[1] or ".mp4"
        compressed_path = os.path.join(temp_dir, f"compressed{ext}")

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", video_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        streams = json.loads(probe.stdout).get("streams", [])
        vid_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        orig_w = int(vid_stream.get("width", 0)) or 0
        orig_h = int(vid_stream.get("height", 0)) or 0

        if orig_w <= target_width:
            debug("compress", f"Video width {orig_w}px ≤ {target_width}px, skipping compression")
            os.rmdir(temp_dir)
            return None

        scale_factor = target_width / orig_w
        new_h = int(orig_h * scale_factor)
        if new_h % 2:
            new_h += 1

        size_before = os.path.getsize(video_path)
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-vf",
                f"scale={target_width}:{new_h}",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "28",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-y",
                compressed_path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )

        size_after = os.path.getsize(compressed_path)
        ratio = (1 - size_after / size_before) * 100 if size_before > 0 else 0
        print(
            f"   → Compressed: {target_width}px, {size_after / 1024 / 1024:.1f} MB ({ratio:.0f}% smaller)", flush=True
        )
        return {"path": compressed_path, "temp_dir": temp_dir}
    except Exception as err:
        warn("compress", f"Video compression failed, using original: {err}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        return None


def _cleanup_temp_dir(results: dict[str, Any]) -> None:
    for key in ("ingest", "compress"):
        temp_dir = results.get("steps", {}).get(key, {}).get("temp_dir") or results.get("steps", {}).get(key, {}).get(
            "output_dir"
        )
        if temp_dir and os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                debug("cleanup", f"Removed {key} temp directory: {temp_dir}")
            except Exception as e:
                warn("cleanup", f"Failed to remove {key} temp directory {temp_dir}: {e}")


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

    sample_result = None
    sampled_path = str(normalized)
    sample_mode = options.get("sample_mode", "full")
    try:
        sample_result = sample_video(str(normalized), options)
        sampled_path = sample_result["path"]
    except Exception as err:
        if sample_mode != "full" and not options.get("force"):
            raise VRError(
                VRErrorCode.SAMPLING_FAILED,
                detail=f"Sampling failed in '{sample_mode}' mode. Use --force to fall back to full video.",
                cause=err,
            ) from err
        warn("sampling", f"Smart sampling failed, using full video: {err}")

    _emit_progress(
        on_progress,
        "step",
        step="resolve",
        status="done",
        message="Video path ready",
        resolved_path=sampled_path,
        video_type=video_type,
        sample_mode=options.get("sample_mode", "full"),
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
        "steps": {"sampling": sample_result},
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
                lambda: ingest_video(sampled_path, options=options, on_progress=None),
                {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                on_retry=lambda a, d, m: _on_retry(
                    "ingest",
                    on_progress,
                    a,
                    d,
                    m,
                    options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                ),
            )
            results["steps"]["ingest"] = step1_data
            _timing["ingest_ms"] = round((time.monotonic() - _t_step) * 1000, 1)

            detected_type = detect_video_type(step1_data.get("video_metadata"), step1_data.get("extraction"))
            info("video-type", f"Detected: {detected_type}")

            if options.get("video_type") and options["video_type"] != detected_type:
                warn("video-type", f"Override: {options['video_type']} (detected: {detected_type})")
                video_type = options["video_type"]
            elif not options.get("video_type"):
                video_type = detected_type
            options["video_type"] = video_type
            results["input"]["video_type"] = video_type
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

        compress_result = _compress_video(sampled_path, options)
        _upload_path = compress_result["path"] if compress_result else sampled_path
        if compress_result:
            results["steps"]["compress"] = compress_result

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

        synthesis_backend = "gemini"
        try:
            if options.get("mock"):
                print("   → Mock mode enabled, skipping API calls", flush=True)
                from src.synthesize_mock import build_blueprint_mock

                blueprint = build_blueprint_mock(_upload_path, results["steps"]["ingest"], options)
                synthesis_backend = "mock"
            else:
                try:
                    blueprint = await with_retry(
                        lambda: build_blueprint(_upload_path, results["steps"]["ingest"], options),
                        {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                        on_retry=lambda a, d, m: _on_retry(
                            "synthesize",
                            on_progress,
                            a,
                            d,
                            m,
                            options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                        ),
                    )
                except Exception as gemini_err:
                    warn("synthesize", f"Gemini failed ({gemini_err})")
                    blueprint = None

                    gemini_fallback_chain = [
                        m
                        for m in [
                            "gemini-2.5-flash",
                            "gemini-2.5-flash-lite",
                            "gemini-3.1-flash-lite",
                            "gemini-3-flash",
                        ]
                        if m != options.get("gemini_model", "")
                    ]
                    for fb_model in gemini_fallback_chain:
                        if options.get("gemini_model") == fb_model:
                            continue
                        print(f"   → Trying lighter Gemini model: {fb_model}...", flush=True)
                        synthesis_backend = f"gemini_{fb_model}"
                        try:
                            fb_options = {**options, "gemini_model": fb_model}
                            blueprint = await with_retry(
                                lambda opts=fb_options: build_blueprint(_upload_path, results["steps"]["ingest"], opts),
                                {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                                on_retry=lambda a, d, m: _on_retry(
                                    "synthesize_gemini_fallback",
                                    on_progress,
                                    a,
                                    d,
                                    m,
                                    options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                                ),
                            )
                            if blueprint:
                                print(f"   → Gemini {fb_model} fallback succeeded", flush=True)
                                break
                        except Exception as fb_err:
                            warn("synthesize", f"Gemini {fb_model} fallback failed ({fb_err})")
                            blueprint = None

                    if not blueprint:
                        openai_key = os.environ.get("OPENAI_API_KEY")
                        if openai_key:
                            warn("synthesize", "Gemini all failed, falling back to OpenAI")
                            print("   → Attempting OpenAI vision fallback...", flush=True)
                            synthesis_backend = "openai"
                            from src.synthesize_openai import build_blueprint_openai

                            try:
                                blueprint = await with_retry(
                                    lambda: build_blueprint_openai(_upload_path, results["steps"]["ingest"], options),
                                    {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                                    on_retry=lambda a, d, m: _on_retry(
                                        "synthesize_openai",
                                        on_progress,
                                        a,
                                        d,
                                        m,
                                        options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                                    ),
                                )
                            except Exception as openai_err:
                                warn("synthesize", f"OpenAI fallback also failed ({openai_err})")

                    if not blueprint:
                        from src.synthesize_free_api import build_blueprint_openrouter

                        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
                        if openrouter_key:
                            synthesis_backend = "openrouter"
                            try:
                                blueprint = await with_retry(
                                    lambda: build_blueprint_openrouter(
                                        _upload_path, results["steps"]["ingest"], options
                                    ),
                                    {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                                    on_retry=lambda a, d, m: _on_retry(
                                        "synthesize_openrouter",
                                        on_progress,
                                        a,
                                        d,
                                        m,
                                        options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                                    ),
                                )
                            except Exception as or_err:
                                warn("synthesize", f"OpenRouter fallback also failed ({or_err})")

                    if not blueprint:
                        from src.synthesize_free_api import build_blueprint_nvidia

                        nvidia_key = os.environ.get("NVIDIA_NIM_API_KEY")
                        if nvidia_key:
                            synthesis_backend = "nvidia"
                            try:
                                blueprint = await with_retry(
                                    lambda: build_blueprint_nvidia(_upload_path, results["steps"]["ingest"], options),
                                    {"maxRetries": options.get("max_retries", RETRY_CONFIG["maxRetries"])},
                                    on_retry=lambda a, d, m: _on_retry(
                                        "synthesize_nvidia",
                                        on_progress,
                                        a,
                                        d,
                                        m,
                                        options.get("max_retries", RETRY_CONFIG["maxRetries"]),
                                    ),
                                )
                            except Exception as nv_err:
                                warn("synthesize", f"NVIDIA fallback also failed ({nv_err})")

                    if not blueprint:
                        raise VRError(
                            VRErrorCode.GEMINI_SYNTHESIS_FAILED,
                            detail="All synthesis backends failed (Gemini, OpenAI, OpenRouter, NVIDIA)",
                        ) from None

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
                "fallback_active": synthesis_backend != "gemini",
                "synthesis_backend": synthesis_backend,
                "template_version": get_template_version(),
                "sampling": sample_result,
            },
        }

        _timing["total_ms"] = round((time.monotonic() - _t_start) * 1000, 1)

        if options.get("dry_run"):
            _emit_progress(
                on_progress,
                "step",
                step="export",
                status="done",
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
            cleanup_sample(sample_result)
            _cleanup_temp_dir(results)
            return results["output"]

        _emit_progress(
            on_progress,
            "step",
            step="export",
            status="running",
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

        cleanup_sample(sample_result)
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

        cleanup_sample(sample_result)
        _cleanup_temp_dir(results)
        raise
