from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory

from utils.cli import (
    DEFAULT_OUTPUT_DIR,
    SUPPORTED_GEMINI_MODELS,
    SUPPORTED_MODELS,
    SUPPORTED_SAMPLE_MODES,
    detect_environment,
)
from web.jobs import JobStore

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
        return jsonify({"error": "No video file uploaded. Choose a video and try again."}), 400

    upload = request.files["video"]
    if not upload.filename:
        return jsonify({"error": "Empty filename."}), 400

    upload_dir = _ensure_upload_dir()
    suffix = Path(upload.filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=upload_dir) as tmp:
        upload.save(tmp.name)
        video_path = tmp.name

    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        os.unlink(video_path)
        return jsonify({"error": f"File too large ({size_mb:.1f} MB). Max is {MAX_UPLOAD_MB} MB."}), 400

    models_raw = request.form.get("models", "")
    models = [m.strip() for m in models_raw.split(",") if m.strip()] or None

    try:
        max_duration = float(request.form["max_duration"]) if request.form.get("max_duration") else None
    except ValueError:
        max_duration = None

    options = {
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
    }

    invalid = [m for m in (models or []) if m not in SUPPORTED_MODELS]
    if invalid:
        os.unlink(video_path)
        return jsonify({"error": f"Unsupported models: {', '.join(invalid)}"}), 400

    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify(
            {
                "error": "GEMINI_API_KEY is not set. Add it to your .env file before running the pipeline.",
            }
        ), 503

    job = job_store.create()
    job_store.start(job, options)

    return jsonify({"job_id": job.id, "filename": upload.filename})


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
    return jsonify({"id": job.id, "status": job.status, "error": job.error, "result": job.result})


def main() -> None:
    host = os.environ.get("VIDEO_REV_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("VIDEO_REV_WEB_PORT", "7860"))
    _ensure_upload_dir()
    print(f"\n  VideoReverse Web UI → http://{host}:{port}\n", flush=True)
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
