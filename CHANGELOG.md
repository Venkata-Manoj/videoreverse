# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Git LFS** — Test videos tracked via Git LFS (`.gitattributes` for `*.mp4`, `*.mov`, `*.avi`, `*.mkv`)
- **Gitleaks** — Secret detection wired into pre-commit hooks
- **mypy strict mode** — `disallow_untyped_defs=true`, `disallow_incomplete_defs=true`, `python_version=3.12`
- **pytest-cov** — Coverage tracking with XML reports
- **Docstrings** — Added to 4 public entry points (`ingest_video`, `build_blueprint`, `compile_prompts`, `format_text`)
- **py.typed** — PEP 561 compliance marker
- **Dynamic versioning** — `__version__` in `src/__init__.py`, single source of truth
- **60 new tests** — Export, rate_limiter, integration mock, fallback chain (103 total)
- **CI improvements** — mypy job, pytest-cov with coverage upload, bandit security scanning
- **Docker improvements** — Pinned base image (`python:3.12.8-slim`), health check, `.dockerignore`
- **Documentation** — `docs/getting-started.md`, `docs/contributing.md`, `docs/faq.md`, `docs/blueprint-schema.md`

### Changed

- Removed `requirements.txt` — `pyproject.toml` is single source of truth
- Removed `MANIFEST.in` — `pyproject.toml` handles packaging
- CI updated from `requirements.txt` to `pyproject.toml` for dependency installation

### Fixed

- Import ordering across `src/` and `utils/` (ruff I001)
- Deprecated `typing.List` usage in `schemas/blueprint.py`
- Exception chaining in `pipeline.py` and `downloader.py` (B904)
- Unused variables in `pipeline.py` (F841)
- Loop variable binding in lambda (B023)

## [2.3.0] - 2026-05-29

### Added

- `utils/rate_limiter.py` — Sliding window rate limiter enforcing per-model RPM (60s), TPM (60s), RPD (86400s) with token estimation (prompt/4 + frames×258 + video_seconds×300)
- `config/model_limits.json` — Per-model free tier limits (RPM, TPM, RPD) for 7 Gemini models, editable without touching code
- **Video compression** — auto-enabled for videos >720px wide (ffmpeg scale=720p, CRF 28, AAC 64k); prints size reduction ratio. Skip with `--no-compress`, adjust with `--compress-width`
- **Frame capping** — after I-frame extraction, down-samples evenly to `--max-frames` (default 60)
- **Upload caching** — Gemini File API uploads cached in memory on retry; file only deleted on success (fixed bug where cached file was deleted on failure causing 403 on retry)
- **Gemini fallback chain** — primary → gemini-2.5-flash → gemini-2.5-flash-lite → gemini-3.1-flash-lite → gemini-3-flash before external API fallbacks
- `--no-compress`, `--compress-width`, `--max-frames`, `--rate-limit-rpm` CLI flags
- `gemini-3.5-flash` model to `SUPPORTED_GEMINI_MODELS`

### Changed

- Default `maxRetries` reduced from 3 to 2 (upload caching makes retries cheaper)
- Primary Gemini model defaults to `gemini-2.5-flash`
- `gemini-2.5-pro`, `gemini-2.0-flash`, `gemini-2.0-flash-lite` removed from supported models (free tier limits are 0/0/0)

### Fixed

- Upload caching: cached file was deleted on failure path (finally block), causing 403 on retry; now only deleted on success
- Pipeline `_compress_video`: missing `import subprocess` causing NameError
- FFprobe width detection: changed from `-show_entries stream=width,height` (no codec_type filter) to `-show_streams` (includes codec_type) to avoid matching non-video streams

## [2.2.0] - 2026-05-28

### Added

- Groq Whisper API as primary transcription backend — uses `whisper-large-v3` via OpenAI-compatible API, falls back to local Whisper automatically
- URL input in Web UI — paste any video URL (YouTube, Vimeo, direct .mp4), downloads via yt-dlp before pipeline
- Searchable checkbox model picker in Web UI — replaces `<select multiple>` with 2-column grid, search/filter, Select All/Deselect All, chip display, and history persistence

### Fixed

- `_analyze_audio_mood` crash on `None` audio codec when video has no audio stream

## [2.1.0] - 2025-06-22

### Added

- Pydantic V2 schema layer (`schemas/blueprint.py`) with `UniversalBlueprint`, `ChronologicalShot`, `GlobalAesthetic`
- Smart sampling: `full`, `first-n`, `highlights` modes via `utils/sampler.py`
- OpenAI GPT-4o mini vision fallback (`src/synthesize_openai.py`)
- SQLite + WAL persistence layer with DB-backed JobManager (`web/db.py`, `web/jobs.py`)
- Luma Ray 2 and Pika 3.0 model templates
- Interactive REPL mode for iterative prompt engineering
- PipelineMetrics collector + `scripts/stats.py` CLI
- API key rotation with per-key usage tracking and 429 fallback
- Profile presets (`--profile fast/quality/cheap`)
- Video-to-video blueprint/prompt diffing (`--compare`)
- Prompt versioning with `--rollback` and `--list-versions`
- Mock mode for offline testing (`src/synthesize_mock.py`)
- Ingest transcription (Whisper) and verification tooling (`scripts/verify_output.py`)
- Batch processing with resume support (`--batch`, `--parallel`)
- Gemini model selection (`--gemini-model`)
- `--max-duration` clipping option

### Changed

- Full codebase migration from Node.js to Python 3.12+
- Tests migrated from custom runner to pytest (41 unit tests)
- Web UI rewritten in Flask with SSE, job history, template editor, monitoring dashboard
- CLI expanded to 20+ flags with WSL/Windows path auto-conversion

### Fixed

- `fallback_active` metadata now correctly reflects whether OpenAI fallback was triggered
- Sampling failure in `first-n`/`highlights` mode now raises a clear error unless `--force` is set
- Path normalization consolidated with proper temp cleanup

## [2.0.0] - 2025-03-10

### Added

- Web UI with live pipeline progress (Flask + SSE)
- Frame-aware blueprint synthesis with shot boundary detection
- Video type detection (CGI, live-action, animation, drone, screen, social, vlog)
- Blueprint caching with SHA-256 keying and 24h TTL
- Error codes (VR-001 through VR-499) with structured error handling
- `utils/validation.py` — Blueprint validation and sanitization
- `utils/retry.py` — Retry logic with exponential backoff + jitter
- `utils/logger.py` — Structured error logging
- Migration script (`scripts/migrate.py`)
- CI/CD (lint, test on Ubuntu/Windows/macOS, PyPI publish, Docker Hub, security scan)

### Changed

- Migrated from Node.js to Python (all `.js` modules replaced with `.py`)
- Unified output persistence to `output_blueprints/` with dual JSON + TXT format

## [1.0.0] - 2024-05-18

### Added

- `pipeline.js` — Main orchestrator chaining all modules
- `ingest.py` — ffmpeg integration, metadata extraction, path normalization
- `synthesize.js` — Gemini File API upload with responseSchema
- `compile.js` — Config-driven prompt compiler
- `export.js` — JSON to human-readable .txt formatter
- `blueprint_prompt.js` — System prompt + JSON schema
- `prompt_templates.json` — 8 video models (Runway, Veo, Kling, Sora, Luma, Pika, Haiper, SVD)
- `utils/` — Error recovery, retry logic, validation, logging, CLI, caching, comparison
- `run_tests.js` — Test runner with validation
- Output persistence to `output_blueprints/` with dual format (.json + .txt)
- Error recovery with graceful degradation
- API rate limit handling with exponential backoff
- JSON validation layer
- CLI with 15+ options (models, format, verbose, etc.)
- Video type detection (CGI, live-action, animation, screen, drone, social)
- Audio mood analysis
- Blueprint caching
- Windows/WSL path handling with UNC support
- Docker support for containerized execution