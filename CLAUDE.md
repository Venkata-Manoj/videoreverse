# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 📋 Project Overview
VideoReverse is a Universal Video-to-Prompt Pipeline that deconstructs any video into production-ready prompts for 8+ video AI models. The workflow follows: Video Input → Ingestion (peepshow) → Blueprint Synthesis (Gemini) → Prompt Compilation (Templates) → Export (JSON/TXT).

## 🔧 Development Commands

### Installation & Setup
```bash
# Install dependencies
npm install

# Install peepshow globally (required for video processing)
npm i -g peepshow

# Configure environment
cp .env.example .env
# Add your GEMINI_API_KEY to .env
```

### Running the Pipeline
```bash
# Basic usage
node src/main.js ./video.mp4

# With specific models
node src/main.js ./video.mp4 --model runway_gen4_5,google_veo3_1

# Dry run (no files saved)
node src/main.js ./video.mp4 --dry-run --verbose

# Using npm scripts
npm start -- ./video.mp4
```

### Testing & Validation
```bash
# Run all tests
npm test

# Run unit tests only
npm test -- tests/unit/

# Run linter
npm run lint

# Validate outputs
npm run validate

# Run full CI pipeline locally
npm run lint && npm test
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
1. **Ingestion** (`src/ingest.js`) - Uses peepshow to extract video/audio metadata, transcripts, and frame analysis
2. **Blueprint Synthesis** (`src/synthesize.js`) - Uses Gemini File API to create universal video blueprint
3. **Prompt Compilation** (`src/compile.js`) - Applies templates to generate model-specific prompts
4. **Export** (`src/export.js`) - Formats output as JSON and/or human-readable text
5. **Path Resolution** (`src/path-resolver.js`) - Handles cross-platform path normalization (Windows/WSL/Linux)

### Key Components
- **CLI Entry Point** (`src/main.js`) - Argument parsing and pipeline orchestration
- **Pipeline Orchestrator** (`src/pipeline.js`) - Manages retry logic, fallback mechanisms, and step timing
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
│   ├── main.js           # CLI entry point
│   ├── pipeline.js       # Main orchestrator with retry/fallback logic
│   ├── ingest.js         # Video ingestion using peepshow
│   ├── synthesize.js     # Gemini-powered blueprint synthesis
│   ├── compile.js        # Template-based prompt compilation
│   ├── export.js         # JSON/TXT output formatting
│   └── path-resolver.js  # Cross-platform path handling
├── config/               # Configuration files
│   └── prompt_templates.json
├── tests/                # Test suite
├── output_blueprints/    # Generated outputs (gitignored)
└── [config files]        # package.json, .env.example, etc.
```

## ⚠️ Important Notes
- Requires Node.js 22+ (use nvm for version management)
- peepshow must be installed globally (`npm i -g peepshow`)
- GEMINI_API_KEY is required in .env file
- Outputs are saved to `output_blueprints/` directory by default
- The project includes comprehensive error handling with helpful messages for common issues (missing peepshow, invalid API key, file not found)
- Supports dry-run mode for testing without saving files
- Implements retry mechanism for API rate limits and transient failures
- Includes fallback blueprint generation when primary synthesis fails

## 🧪 Testing Guidelines
- Test videos are referenced in README (test1.mp4 for CGI/Animation)
- Unit tests should mock external dependencies (peepshow, Gemini API)
- Integration tests can use actual test videos
- Linting follows standard JavaScript conventions
- Validation ensures output matches expected schema

## 🔄 CI/CD Workflows
- CI runs on push/PR across Ubuntu, Windows, and macOS
- Release workflow triggered by tags for npm publish + Docker Hub
- Weekly security scans for secret scanning and SBOM generation