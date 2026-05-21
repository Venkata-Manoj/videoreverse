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
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GEMINI_API_KEY` | Gemini API key for blueprint synthesis | — | ✅ |
| `VIDEO_REV_OUTPUT_DIR` | Output directory | `output_blueprints/` | ❌ |
| `VIDEO_REV_CONFIG_DIR` | Config directory | `config/` | ❌ |
| `VIDEO_REV_LOG_LEVEL` | Log level: `debug`, `info`, `warn`, `error`, `quiet` | `info` | ❌ |

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
| `--max-retries, -r` | API retry attempts | `3` |
| `--max-duration` | Pre-clip video to N seconds | — |
| `--video-type` | Override auto-detected video type | Auto |
| `--no-cache` | Disable blueprint caching | `false` |
| `--wsl` | Force WSL path conversion | Auto |
| `--win` | Force Windows path mode | Auto |

---

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Video     │────▶│   Ingest    │────▶│  Synthesize │────▶│   Compile   │────▶│   Export    │
│   Input     │     │   (ffmpeg)  │     │   (Gemini)  │     │  (Templates)│     │ (JSON/TXT)  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                        │                    │                    │                    │
                   metadata            blueprint             prompts             output
                   + audio              + shots               + model             files
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
python -m src.run_tests

# Run unit tests
python -c "from tests.unit import test_validation, test_compile, test_retry; test_validation.run_tests(); test_compile.run_tests(); test_retry.run_tests()"

# Run linter
python scripts/lint.py

# Validate outputs
python scripts/validate.py

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
│   └── prompt_templates.json
├── utils/                # Shared utilities
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
| Python | 3.11+ |
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
