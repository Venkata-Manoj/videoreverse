# Getting Started

## Prerequisites

- **Python 3.12+** (use `pyenv install 3.12` if needed)
- **ffmpeg** for video processing
- **GEMINI_API_KEY** in `.env` file (required for blueprint synthesis)

## Installation

### Option 1: Docker (fastest)

```bash
git clone https://github.com/Venkata-Manoj/videoreverse.git
cd videoreverse
cp .env.example .env  # Add your GEMINI_API_KEY
docker compose run --rm vidrev src.main ./video.mp4
```

### Option 2: pip install

```bash
pip install vidrev
vidrev ./video.mp4
```

### Option 3: From source

```bash
git clone https://github.com/Venkata-Manoj/videoreverse.git
cd videoreverse
pip install -e ".[dev,web]"
cp .env.example .env  # Add your GEMINI_API_KEY
python -m src.main ./video.mp4
```

## Quick Start

### 1. Add your API key

```bash
echo "GEMINI_API_KEY=your_key_here" > .env
```

### 2. Run the pipeline

```bash
# Basic usage
python -m src.main ./video.mp4

# No API key? Use mock mode
python -m src.main ./video.mp4 --mock

# Specific models only
python -m src.main ./video.mp4 -m runway_gen4_5,google_veo3_1
```

### 3. View output

Output is saved to `output_blueprints/` as both `.json` and `.txt` files.

### 4. Web UI

```bash
python -m web
# Open http://localhost:7860
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key for video analysis |
| `OPENAI_API_KEY` | No | OpenAI API key for fallback |
| `OPENROUTER_API_KEY` | No | OpenRouter API key for free fallback |
| `NVIDIA_NIM_API_KEY` | No | NVIDIA NIM API key for free fallback |
| `GROQ_API_KEY` | No | Groq API key for faster transcription |

## Next Steps

- [CLI Reference](cli-reference.md) — All available options
- [Architecture](architecture.md) — How the pipeline works
- [FAQ](faq.md) — Common issues and solutions
