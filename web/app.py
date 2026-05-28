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
from utils.downloader import download_video, is_valid_video_url
from utils.error_codes import VRError
from utils.logger import info
from web.jobs import JobManager

load_dotenv()

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
UPLOAD_DIR = Path(os.environ.get("VIDEO_REV_WEB_UPLOAD_DIR", ".cache/web_uploads"))
MAX_UPLOAD_MB = int(os.environ.get("VIDEO_REV_WEB_MAX_MB", "500"))

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
job_manager = JobManager()


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
        return "file_too_large"

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
        "max_retries": int(request.form.get("max_retries") or 3),
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


@app.post("/api/run-url")
def run_url_job() -> Response:
    url = request.form.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    if not is_valid_video_url(url):
        return jsonify({"error": "Invalid URL format"}), 400

    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"error": "GEMINI_API_KEY not configured"}), 503

    try:
        upload_dir = _ensure_upload_dir()
        video_path = download_video(url, str(upload_dir), MAX_UPLOAD_MB)
    except VRError as e:
        return jsonify({"error": e.detail or str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Download failed: {e}"}), 400

    models_raw = request.form.get("models", "")
    models = [m.strip() for m in models_raw.split(",") if m.strip()] or None
    options = _build_options(video_path, models)

    invalid = [m for m in (models or []) if m not in SUPPORTED_MODELS]
    if invalid:
        os.unlink(video_path)
        return jsonify({"error": f"Unsupported models: {', '.join(invalid)}"}), 400

    job_id = job_manager.create_job()
    job_manager.start_pipeline(job_id, options)

    return jsonify({"job_id": job_id, "filename": Path(video_path).name})


@app.post("/api/run")
def run_pipeline_job() -> Response:
    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    upload = request.files["video"]
    if not upload.filename:
        return jsonify({"error": "No video file provided"}), 400

    try:
        video_path = _save_upload(upload)
    except ValueError:
        return jsonify({"error": "File upload failed"}), 400

    if video_path == "file_too_large":
        return jsonify({"error": f"File exceeds {MAX_UPLOAD_MB}MB limit"}), 400

    models_raw = request.form.get("models", "")
    models = [m.strip() for m in models_raw.split(",") if m.strip()] or None
    options = _build_options(video_path, models)

    invalid = [m for m in (models or []) if m not in SUPPORTED_MODELS]
    if invalid:
        os.unlink(video_path)
        return jsonify({"error": f"Unsupported models: {', '.join(invalid)}"}), 400

    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"error": "GEMINI_API_KEY not configured"}), 503

    job_id = job_manager.create_job()
    job_manager.start_pipeline(job_id, options)

    return jsonify({"job_id": job_id, "filename": upload.filename})


@app.post("/api/run-batch")
def run_batch_job() -> Response:
    uploads = [upload for upload in request.files.getlist("videos") if upload and upload.filename]
    if not uploads:
        return jsonify({"error": "No video files provided"}), 400

    models_raw = request.form.get("models", "")
    models = [m.strip() for m in models_raw.split(",") if m.strip()] or None
    invalid = [m for m in (models or []) if m not in SUPPORTED_MODELS]
    if invalid:
        return jsonify({"error": f"Unsupported models: {', '.join(invalid)}"}), 400

    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"error": "GEMINI_API_KEY not configured"}), 503

    video_paths: list[str] = []
    try:
        for upload in uploads:
            video_path = _save_upload(upload)
            if video_path == "file_too_large":
                for path in video_paths:
                    if os.path.exists(path):
                        os.unlink(path)
                return jsonify({"error": f"File exceeds {MAX_UPLOAD_MB}MB limit"}), 400
            video_paths.append(video_path)
    except ValueError:
        for path in video_paths:
            if os.path.exists(path):
                os.unlink(path)
        return jsonify({"error": "File upload failed"}), 400

    options = _build_options(video_paths[0], models)
    job_id = job_manager.create_job()
    job_manager.start_batch(job_id, video_paths, options)
    return jsonify({"job_id": job_id, "filenames": [upload.filename for upload in uploads], "count": len(uploads)})


@app.get("/api/jobs/<job_id>/stream")
def stream_job(job_id: str) -> Response:
    return Response(
        job_manager.iter_events(job_id),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str) -> Response:
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"id": job["id"], "status": job["status"], "error": job.get("error"), "result": job.get("result"), "files": job.get("files", {})})


@app.get("/api/jobs/<job_id>/download/<artifact>")
def download_artifact(job_id: str, artifact: str) -> Response:
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    artifact_path = job.get("files", {}).get(artifact)
    if not artifact_path:
        return jsonify({"error": "Artifact not found"}), 404

    resolved = Path(artifact_path).resolve()
    if not resolved.exists():
        return jsonify({"error": "Artifact missing on disk"}), 404

    return send_file(resolved, as_attachment=True, download_name=resolved.name)


@app.route("/api/templates", methods=["GET"])
def get_templates() -> Response:
    templates_path = Path("config/prompt_templates.json")
    if not templates_path.exists():
        return jsonify({"error": "Templates file not found"}), 404
    with open(templates_path, encoding="utf-8") as f:
        templates = json.load(f)
    model_names = list(templates.keys())
    return jsonify({
        "templates": templates,
        "models": model_names,
        "default_template": templates.get(model_names[0]) if model_names else None,
    })


@app.route("/api/templates/<model_id>", methods=["GET"])
def get_template(model_id: str) -> Response:
    templates_path = Path("config/prompt_templates.json")
    if not templates_path.exists():
        return jsonify({"error": "Templates file not found"}), 404
    with open(templates_path, encoding="utf-8") as f:
        templates = json.load(f)
    if model_id not in templates:
        return jsonify({"error": f"Model '{model_id}' not found"}), 404
    return jsonify(templates[model_id])


@app.route("/api/templates/<model_id>", methods=["PUT"])
def update_template(model_id: str) -> Response:
    templates_path = Path("config/prompt_templates.json")
    if not templates_path.exists():
        return jsonify({"error": "Templates file not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    with open(templates_path, encoding="utf-8") as f:
        templates = json.load(f)

    if model_id not in templates:
        return jsonify({"error": f"Model '{model_id}' not found"}), 404

    existing = templates[model_id]
    for key in ("template", "label", "supports_negative", "max_duration", "aspect_ratio_support", "negative_placeholder", "notes", "enhancement_rules"):
        if key in data:
            existing[key] = data[key]

    with open(templates_path, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2)

    info("web", f"Template '{model_id}' updated via web UI")
    return jsonify({"ok": True, "model": model_id, "template": existing})


def main() -> None:
    host = os.environ.get("VIDEO_REV_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("VIDEO_REV_WEB_PORT", "7860"))
    _ensure_upload_dir()

    cleaned = job_manager.cleanup_old_jobs(max_age_hours=24)
    if cleaned:
        info("web", f"Cleaned up {cleaned} old job(s) older than 24h")

    print(f"\n  VideoReverse Web UI → http://{host}:{port}\n", flush=True)
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
