# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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