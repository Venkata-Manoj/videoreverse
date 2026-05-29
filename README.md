# VideoReverse

**Universal Video-to-Prompt Pipeline** — deconstruct any video into production-ready prompts for 8+ video AI models.

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![CI](https://github.com/Venkata-Manoj/videoreverse/workflows/CI/badge.svg)](https://github.com/Venkata-Manoj/videoreverse/actions)
[![GitHub stars](https://img.shields.io/github/stars/Venkata-Manoj/videoreverse)](https://github.com/Venkata-Manoj/videoreverse/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/Venkata-Manoj/videoreverse)](https://github.com/Venkata-Manoj/videoreverse/issues)

---

## 📌 Overview

VideoReverse analyzes videos using AI to generate production-ready prompts for video generation models. It deconstructs video into a universal blueprint, then compiles model-specific prompts for:

| Model | Max Duration | Negative Prompts |
|-------|-------------|-----------------|
| Runway Gen-4.5 | 16s | ❌ |
| Google Veo 3.1 | 60s | ✅ |
| Kling 3.0 | 30s | ✅ |
| OpenAI Sora 2 | 60s | ✅ |
| Luma Dream Machine | 12s | ❌ |
| Pika 2.0 | 10s | ✅ |
| Haiper 2.0 | 8s | ❌ |
| Stable Video Diffusion | 4s | ✅ |

**Current Focus:** Quality and Accuracy

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** — [Install via pyenv](https://github.com/pyenv/pyenv)
- **ffmpeg** — for smart sampling (`apt install ffmpeg` or `brew install ffmpeg`)
- **GEMINI_API_KEY** — Get from [Google AI Studio](https://aistudio.google.com/)

Transcription uses **Groq Whisper API** (`whisper-large-v3`) when `GROQ_API_KEY` is set — falls back to local Whisper automatically. Local transcription is included in the default `requirements.txt` install. For editable installs, `pip install -e ".[whisper]"` adds Whisper explicitly.

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Venkata-Manoj/videoreverse.git
cd videoreverse

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Run

```bash
# Full pipeline
python -m src.main ./video.mp4

# Specific models
python -m src.main ./video.mp4 --model runway_gen4_5,google_veo3_1

# Dry run (no files saved)
python -m src.main ./video.mp4 --dry-run --verbose

# Use a specific Gemini model
python -m src.main ./video.mp4 --gemini-model gemini-3.5-flash
```

Add `--no-transcribe` to skip local Whisper transcription during ingest.  
Add `--mock` to generate a synthetic blueprint from metadata without any API calls (zero cost).

### Web UI (browser testing)

For non-technical testers, use the built-in Web UI. It shows each pipeline step in real time (prepare → ingest → blueprint → compile → export), supports file upload and **URL input** (YouTube/Vimeo/direct links auto-download via yt-dlp), a searchable **model checkbox picker** with Select All/None, multi-file batch queue, and lets users download saved outputs or copy generated prompts directly from the browser.

```bash
pip install flask
# or: pip install -e ".[web]"

python -m web
# Open http://127.0.0.1:7860 — upload a video and click Start analysis
```

Optional env vars: `VIDEO_REV_WEB_HOST`, `VIDEO_REV_WEB_PORT` (default `7860`), `VIDEO_REV_WEB_MAX_MB` (default `500`).

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GEMINI_API_KEY` | Gemini API key for blueprint synthesis | — | ✅ |
| `OPENAI_API_KEY` | OpenAI API key for fallback synthesis (when Gemini is unavailable) | — | ❌ |
| `GROQ_API_KEY` | Groq API key for Whisper transcription (`whisper-large-v3`) | — | ❌ |
| `VIDEO_REV_OUTPUT_DIR` | Output directory | `output_blueprints/` | ❌ |
| `VIDEO_REV_CONFIG_DIR` | Config directory | `config/` | ❌ |
| `VIDEO_REV_LOG_LEVEL` | Log level: `debug`, `info`, `warn`, `error`, `quiet` | `info` | ❌ |

### Supported Gemini Models

| Model | RPM | TPM | RPD | Notes |
|-------|-----|-----|-----|-------|
| `gemini-2.5-flash` | 3 | 2,110 | 11 | Default, good quality/rate balance |
| `gemini-3.5-flash` | 1 | 1,960 | 2 | Latest, best quality, very limited |
| `gemini-2.5-flash-lite` | 2 | 1,390 | 4 | Lighter, faster |
| `gemini-3.1-flash-lite` | 15 | 250K | 500 | High rate limit, lower quality |
| `gemini-3-flash` | 5 | 250K | 20 | Good fallback |
| `gemini-flash-latest` | 3 | 2,110 | 11 | Alias for 2.5-flash |
| `gemini-flash-lite-latest` | 2 | 1,390 | 4 | Alias for 2.5-flash-lite |

Limits are enforced by the sliding window rate limiter (`utils/rate_limiter.py`) before each API call. If a model's RPM/TPM/RPD is exhausted, the pipeline automatically falls back through lighter Gemini models before trying external APIs.

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--help, -h` | Show help message | — |
| `--model, -m` | Generate for specific models (comma-separated) | All models |
| `--output-dir, -o` | Custom output directory | `output_blueprints/` |
| `--format` | Output format: `json`, `txt`, `both`, `none` | `both` |
| `--verbose, -v` | Debug logging | `false` |
| `--quiet, -q` | Suppress console output | `false` |
| `--dry-run` | Output without saving files | `false` |
| `--force, -F` | Skip failed steps, use cached results | `false` |
| `--max-retries, -r` | API retry attempts | `2` |
| `--max-frames` | Max frames to extract (reduces token usage) | `60` |
| `--max-duration` | Pre-clip video to N seconds | — |
| `--sample-mode` | Sampling: `full`, `first-n`, `highlights` | `full` |
| `--video-type` | Override auto-detected video type | Auto |
| `--no-compress` | Skip video compression before API upload | `false` |
| `--compress-width` | Target width for compression (min: 360) | `720` |
| `--no-cache` | Disable blueprint caching | `false` |
| `--no-transcribe` | Skip local Whisper transcription | `false` |
| `--rate-limit-rpm` | Max API requests per minute | `5` |
| `--gemini-model` | Gemini model for analysis | `gemini-2.5-flash` |
| `--mock` | Skip API calls, synthetic blueprint | `false` |
| `--wsl` | Force WSL path conversion | Auto |
| `--win` | Force Windows path mode | Auto |

---

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐     ┌─────────────┐     ┌─────────────┐
│   Video     │────▶│   Ingest    │────▶│   Synthesize     │────▶│   Compile   │────▶│   Export    │
│   Input     │     │   (ffmpeg)  │     │  (Gemini chain)  │     │  (Templates)│     │ (JSON/TXT)  │
└─────────────┘     └──────┬──────┘     └────────┬─────────┘     └─────────────┘     └─────────────┘
                           │                      │
                      metadata + audio       fallback chain:
                      + compressed video     gemini-2.5-flash →
                      + capped frames        gemini-2.5-flash-lite →
                                             gemini-3.1-flash-lite →
                                             gemini-3-flash →
                                             OpenAI GPT-4o mini →
                                             OpenRouter Kimi K2.6 →
                                             NVIDIA Nemotron VL 8B
```

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `main.py` | `src/` | CLI entry point, argument parsing |
| `pipeline.py` | `src/` | Orchestrator, chains all modules |
| `ingest.py` | `src/` | Video metadata extraction, audio analysis |
| `synthesize.py` | `src/` | Gemini File API integration |
| `compile.py` | `src/` | Prompt compilation from templates |
| `export.py` | `src/` | JSON to human-readable TXT formatter |
| `path_resolver.py` | `src/` | Cross-platform path normalization |

### Universal Blueprint Schema

```json
{
  "global_aesthetic": {
    "art_style": "cinematic",
    "color_grading": "warm",
    "lighting_setup": "natural"
  },
  "chronological_shots": [
    {
      "shot_index": 0,
      "duration_seconds": 5.0,
      "camera_direction": "static",
      "framing_type": "wide",
      "action_and_motion": "character walking",
      "environment_context": "forest",
      "negative_elements": ["blur", "noise"]
    }
  ]
}
```

---

## 🧪 Testing & Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
python -m pytest tests/unit/

# Run linter
python scripts/lint.py

# Validate outputs
python scripts/validate.py

# Verify the latest saved output for a video without rerunning the pipeline
python scripts/verify_output.py test1.mp4 --strict

# Run with Docker
docker build -t vidrev .
docker run -v ./videos:/data/videos -e GEMINI_API_KEY=your_key vidrev ./data/videos/input.mp4
```

### Test Videos

| File | Description | Required |
|------|-------------|----------|
| `test1.mp4` | CGI/Animation | ✅ |
| `test_drone.mp4` | Aerial footage | ❌ |
| `test_anime.mp4` | 2D Animation | ❌ |
| `test_vlog.mp4` | Handheld multi-cut | ❌ |

---

## 🔄 CI/CD

### Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| [`ci.yml`](.github/workflows/ci.yml) | Push/PR | Lint + Tests on Ubuntu, Windows, macOS |
| [`release.yml`](.github/workflows/release.yml) | Tag | PyPI publish + Docker Hub |
| [`security-scan.yml`](.github/workflows/security-scan.yml) | Weekly | Secret scanning + SBOM |

### Local CI Simulation

```bash
# Run the full CI pipeline locally
python scripts/lint.py && python -m src.run_tests
```

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

```bash
# 1. Fork the repository
# 2. Create a feature branch
git checkout -b feature/my-feature

# 3. Make changes and test
python -m src.run_tests

# 4. Commit with clear message
git commit -m "feat(scope): description"

# 5. Push and open PR
git push origin feature/my-feature
```

### Commit Message Format

```
type(scope): description

Types: feat, fix, docs, refactor, test, chore
```

---

## 📜 License

MIT License — see [LICENSE](./LICENSE) for details.

---

## 🔒 Security

See [SECURITY.md](./SECURITY.md) for vulnerability reporting.

**Key practices:**
- Never commit `.env` files
- Rotate `GEMINI_API_KEY` regularly
- Use `.env.example` as template

---

## 📞 Support

- **GitHub Issues:** [Open an issue](https://github.com/Venkata-Manoj/videoreverse/issues)

---

## 🗂️ Project Structure

```
videoreverse/
├── src/                  # Source code
│   ├── main.py           # CLI entry point
│   ├── pipeline.py       # Main orchestrator
│   ├── ingest.py         # Video ingestion
│   ├── synthesize.py     # Gemini synthesis
│   ├── compile.py        # Prompt compiler
│   ├── export.py         # Output formatter
│   ├── path_resolver.py  # Path normalization
│   └── run_tests.py      # Test runner
├── config/               # Configuration
│   ├── prompt_templates.json
│   └── model_limits.json     # Per-model free tier limits
├── utils/                # Shared utilities
│   └── rate_limiter.py   # Per-model RPM/TPM/RPD limiter
├── tests/                # Test suite
├── scripts/              # Dev automation
├── docs/                 # Documentation
├── .github/              # CI/CD workflows
├── output_blueprints/    # Generated outputs (gitignored)
└── [config files]        # requirements.txt, Dockerfile, etc.
```

---

## 📋 Compatibility Matrix

| Component | Supported Versions |
|-----------|-------------------|
| Python | 3.12+ |
| ffmpeg | Latest |
| Gemini API | v1 |
| OS | Ubuntu, Windows (WSL), macOS |
| Video formats | MP4, MOV, AVI, WebM (ffmpeg-supported) |

<!-- TODO: Add architecture diagram -->
<!-- ![Architecture](./docs/architecture.png) -->

<!-- TODO: Add contributing statistics badge -->
<!-- ![Contributors](https://img.shields.io/github/contributors/Venkata-Manoj/videoreverse) -->

<!-- TODO: Add CodeQL status badge -->
<!-- [![CodeQL](https://github.com/Venkata-Manoj/videoreverse/actions/workflows/codeql.yml/badge.svg)](https://github.com/Venkata-Manoj/videoreverse/actions/workflows/codeql.yml) -->
