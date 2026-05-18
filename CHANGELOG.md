# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-05-18

### Added

- `pipeline.js` — Main orchestrator chaining all modules
- `ingest.js` — peepshow CLI integration, metadata extraction, path normalization
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