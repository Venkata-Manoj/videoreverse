# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 📋 Project Overview
VideoReverse is a Universal Video-to-Prompt Pipeline that deconstructs any video into production-ready prompts for 8+ video AI models. The workflow follows: Video Input → Ingestion (ffmpeg) → Blueprint Synthesis (Gemini) → Prompt Compilation (Templates) → Export (JSON/TXT).

## 🔧 Development Commands

### Installation & Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add your GEMINI_API_KEY to .env
```

### Running the Pipeline
```bash
# Basic usage
python -m src.main ./video.mp4

# With specific models
python -m src.main ./video.mp4 --model runway_gen4_5,google_veo3_1

# Dry run (no files saved)
python -m src.main ./video.mp4 --dry-run --verbose
```

### Testing & Validation
```bash
# Run all tests
python -m src.run_tests

# Run linter
python scripts/lint.py

# Validate outputs
python scripts/validate.py

# Run full CI pipeline locally
python scripts/lint.py && python -m src.run_tests
```

### Docker Usage
```bash
# Build Docker image
docker build -t vidrev .

# Run with Docker
docker run -v ./videos:/data/videos -e GEMINI_API_KEY=your_key vidrev ./data/videos/input.mp4
```

## 🏗️ Architecture Overview

### Core Pipeline Flow
1. **Ingestion** (`src/ingest.py`) - Uses ffmpeg to extract video/audio metadata, transcripts, and frame analysis
2. **Blueprint Synthesis** (`src/synthesize.py`) - Uses Gemini File API to create universal video blueprint
3. **Prompt Compilation** (`src/compile.py`) - Applies templates to generate model-specific prompts
4. **Export** (`src/export.py`) - Formats output as JSON and/or human-readable text
5. **Path Resolution** (`src/path_resolver.py`) - Handles cross-platform path normalization (Windows/WSL/Linux)

### Key Components
- **CLI Entry Point** (`src/main.py`) - Argument parsing and pipeline orchestration
- **Pipeline Orchestrator** (`src/pipeline.py`) - Manages retry logic, fallback mechanisms, and step timing
- **Universal Blueprint Schema** - Structured representation with global aesthetics and chronological shots
- **Fallback System** - Graceful degradation when Gemini API fails
- **Video Type Detection** - Automatic detection of video content type (animation, aerial, vlog, etc.)

### Configuration
- Environment variables: `GEMINI_API_KEY`, `VIDEO_REV_OUTPUT_DIR`, `VIDEO_REV_CONFIG_DIR`, `VIDEO_REV_LOG_LEVEL`
- CLI options for model selection, output format, retries, duration limits, and caching control
- Prompt templates stored in `config/prompt_templates.json`

## 📁 Project Structure
```
videoreverse/
├── src/                  # Source code
│   ├── main.py           # CLI entry point
│   ├── pipeline.py       # Main orchestrator with retry/fallback logic
│   ├── ingest.py         # Video ingestion using ffmpeg
│   ├── synthesize.py     # Gemini-powered blueprint synthesis
│   ├── compile.py        # Template-based prompt compilation
│   ├── export.py         # JSON/TXT output formatting
│   └── path_resolver.py  # Cross-platform path handling
├── config/               # Configuration files
│   └── prompt_templates.json
├── tests/                # Test suite
├── output_blueprints/    # Generated outputs (gitignored)
└── [config files]        # requirements.txt, .env.example, etc.
```

## ⚠️ Important Notes
- Requires Python 3.12+ (use pyenv for version management)
- GEMINI_API_KEY is required in .env file
- Outputs are saved to `output_blueprints/` directory by default
- The project includes comprehensive error handling with helpful messages for common issues (missing ffmpeg, invalid API key, file not found)
- Supports dry-run mode for testing without saving files
- Implements retry mechanism for API rate limits and transient failures
- Includes fallback blueprint generation when primary synthesis fails

## 🧪 Testing Guidelines
- Test videos are referenced in README (test1.mp4 for CGI/Animation)
- Unit tests should mock external dependencies (ffmpeg, Gemini API)
- Integration tests can use actual test videos
- Linting follows Python conventions
- Validation ensures output matches expected schema

## 🔄 CI/CD Workflows
- CI runs on push/PR across Ubuntu, Windows, and macOS
- Release workflow triggered by tags for PyPI publish + Docker Hub
- Weekly security scans for secret scanning and SBOM generation
