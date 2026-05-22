from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_file, send_from_directory

from utils.cli import (
    DEFAULT_OUTPUT_DIR,
    SUPPORTED_GEMINI_MODELS,
    SUPPORTED_MODELS,
    SUPPORTED_SAMPLE_MODES,
    detect_environment,
)
from web.jobs import JobStore
from web.utils.error_codes import VRLErrorCode, format_user_friendly_error, get_error_details

load_dotenv()

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
UPLOAD_DIR = Path(os.environ.get("VIDEO_REV_WEB_UPLOAD_DIR", ".cache/web_uploads"))
MAX_UPLOAD_MB = int(os.environ.get("VIDEO_REV_WEB_MAX_MB", "500"))

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
job_store = JobStore()


def _ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def _save_upload(upload) -> str:
    upload_dir = _ensure_upload_dir()
    suffix = Path(upload.filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=upload_dir) as tmp:
        upload.save(tmp.name)
        video_path = tmp.name

    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        os.unlink(video_path)
        raise ValueError("file_too_large")

    return video_path


def _build_options(video_path: str, models: list[str] | None) -> dict[str, object]:
    try:
        max_duration = float(request.form["max_duration"]) if request.form.get("max_duration") else None
    except ValueError:
        max_duration = None

    return {
        "video_path": video_path,
        "models": models,
        "output_dir": request.form.get("output_dir") or DEFAULT_OUTPUT_DIR,
        "format": request.form.get("format") or "both",
        "dry_run": request.form.get("dry_run") == "true",
        "max_retries": int(request.form.get("max_retries") or 5),
        "use_fallback": request.form.get("use_fallback", "true") == "true",
        "max_duration": max_duration,
        "sample_mode": request.form.get("sample_mode") or "full",
        "gemini_model": request.form.get("gemini_model") or "gemini-2.5-flash",
        "no_cache": request.form.get("no_cache") == "true",
        "no_transcribe": request.form.get("no_transcribe") == "true",
    }


@app.route("/")
def index() -> Response:
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/health")
def health() -> Response:
    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    return jsonify(
        {
            "ok": True,
            "environment": detect_environment(),
            "gemini_configured": has_key,
        }
    )


@app.get("/api/config")
def config() -> Response:
    templates_path = Path("config/prompt_templates.json")
    labels: dict[str, str] = {}
    if templates_path.exists():
        with open(templates_path, encoding="utf-8") as f:
            raw = json.load(f)
        labels = {key: val.get("label", key) for key, val in raw.items() if key in SUPPORTED_MODELS}

    models = [{"id": m, "label": labels.get(m, m.replace("_", " ").title())} for m in SUPPORTED_MODELS]
    return jsonify(
        {
            "models": models,
            "sample_modes": SUPPORTED_SAMPLE_MODES,
            "gemini_models": SUPPORTED_GEMINI_MODELS,
            "default_output_dir": DEFAULT_OUTPUT_DIR,
            "max_upload_mb": MAX_UPLOAD_MB,
        }
    )


@app.post("/api/run")
def run_pipeline_job() -> Response:
    if "video" not in request.files:
        error = VRLErrorCode.NO_VIDEO_FILE
        return jsonify({"error": format_user_friendly_error(error)}), 400

    upload = request.files["video"]
    if not upload.filename:
        error = VRLErrorCode.NO_VIDEO_FILE
        return jsonify({"error": format_user_friendly_error(error)}), 400

    try:
        video_path = _save_upload(upload)
    except ValueError:
        error = VRLErrorCode.FILE_TOO_LARGE
        return jsonify({"error": format_user_friendly_error(error)}), 400

    models_raw = request.form.get("models", "")
    models = [m.strip() for m in models_raw.split(",") if m.strip()] or None
    options = _build_options(video_path, models)

    invalid = [m for m in (models or []) if m not in SUPPORTED_MODELS]
    if invalid:
        os.unlink(video_path)
        error_details = get_error_details(VRLErrorCode.UNSUPPORTED_FORMAT)
        error_details["details"] = f"Unsupported models: {', '.join(invalid)}"
        return jsonify({"error": format_user_friendly_error(VRLErrorCode.UNSUPPORTED_FORMAT), "error_details": error_details}), 400

    if not os.environ.get("GEMINI_API_KEY"):
        error_details = get_error_details(VRLErrorCode.GEMINI_API_KEY_MISSING)
        return jsonify({"error": format_user_friendly_error(VRLErrorCode.GEMINI_API_KEY_MISSING), "error_details": error_details}), 503

    job = job_store.create()
    job_store.start(job, options)

    return jsonify({"job_id": job.id, "filename": upload.filename})


@app.post("/api/run-batch")
def run_batch_job() -> Response:
    uploads = [upload for upload in request.files.getlist("videos") if upload and upload.filename]
    if not uploads:
        error = VRLErrorCode.NO_VIDEO_FILE
        return jsonify({"error": format_user_friendly_error(error)}), 400

    models_raw = request.form.get("models", "")
    models = [m.strip() for m in models_raw.split(",") if m.strip()] or None
    invalid = [m for m in (models or []) if m not in SUPPORTED_MODELS]
    if invalid:
        error_details = get_error_details(VRLErrorCode.UNSUPPORTED_FORMAT)
        error_details["details"] = f"Unsupported models: {', '.join(invalid)}"
        return jsonify({"error": format_user_friendly_error(VRLErrorCode.UNSUPPORTED_FORMAT), "error_details": error_details}), 400

    if not os.environ.get("GEMINI_API_KEY"):
        error_details = get_error_details(VRLErrorCode.GEMINI_API_KEY_MISSING)
        return jsonify({"error": format_user_friendly_error(VRLErrorCode.GEMINI_API_KEY_MISSING), "error_details": error_details}), 503

    video_paths: list[str] = []
    try:
        for upload in uploads:
            video_paths.append(_save_upload(upload))
    except ValueError:
        for video_path in video_paths:
            if os.path.exists(video_path):
                os.unlink(video_path)
        error = VRLErrorCode.FILE_TOO_LARGE
        return jsonify({"error": format_user_friendly_error(error)}), 400

    options = _build_options(video_paths[0], models)
    job = job_store.create()
    job_store.start_batch(job, video_paths, options)
    return jsonify({"job_id": job.id, "filenames": [upload.filename for upload in uploads], "count": len(uploads)})


@app.get("/api/jobs/<job_id>/stream")
def stream_job(job_id: str) -> Response:
    return Response(
        job_store.iter_events(job_id),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str) -> Response:
    job = job_store.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"id": job.id, "status": job.status, "error": job.error, "result": job.result, "files": job.files})


@app.get("/api/jobs/<job_id>/download/<artifact>")
def download_artifact(job_id: str, artifact: str) -> Response:
    job = job_store.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    artifact_path = job.files.get(artifact)
    if not artifact_path:
        return jsonify({"error": "Artifact not found"}), 404

    resolved = Path(artifact_path).resolve()
    if not resolved.exists():
        return jsonify({"error": "Artifact missing on disk"}), 404

    return send_file(resolved, as_attachment=True, download_name=resolved.name)


def main() -> None:
    host = os.environ.get("VIDEO_REV_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("VIDEO_REV_WEB_PORT", "7860"))
    _ensure_upload_dir()
    print(f"\n  VideoReverse Web UI → http://{host}:{port}\n", flush=True)
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
