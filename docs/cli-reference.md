# VideoReverse — CLI Reference

## Commands

### Main Pipeline
```bash
python -m src.main <video_path_or_url> [options]
```

### Individual Modules
```bash
python -m src.pipeline <video>      # Full pipeline
python -m src.ingest <video>        # Ingestion only
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--help, -h` | Show help message | - |
| `--model, -m` | Specific models (comma-separated) | All models |
| `--output-dir, -o` | Output directory | `output_blueprints/` |
| `--format` | Output format: `json`, `txt`, `both`, `none` | `both` |
| `--log-level, -l` | Log level: `debug`, `info`, `warn`, `error`, `quiet` | `info` |
| `--verbose, -v` | Enable debug logging | `false` |
| `--quiet, -q` | Suppress console output | `false` |
| `--dry-run` | Output without saving files | `false` |
| `--force, -F` | Skip failed steps | `false` |
| `--max-retries, -r` | API retry attempts | `2` |
| `--max-frames` | Max frames to extract (reduces token usage) | `60` |
| `--max-duration` | Pre-clip to N seconds | - |
| `--sample-mode` | Sampling: `full`, `first-n`, `highlights` | `full` |
| `--video-type` | Override video type detection | Auto |
| `--no-compress` | Skip video compression before API upload | `false` |
| `--compress-width` | Target width for compression (min: 360) | `720` |
| `--no-cache` | Disable blueprint caching | `false` |
| `--rate-limit-rpm` | Max API requests per minute | `5` |
| `--gemini-model` | Gemini model for analysis | `gemini-2.5-flash` |
| `--mock` | Skip API calls, synthetic blueprint from metadata | `false` |
| `--wsl` | Force WSL path mode | Auto |
| `--win` | Force Windows path mode | Auto |

## Examples

```bash
# Basic usage
python -m src.main ./video.mp4

# Specific models
python -m src.main ./video.mp4 --model runway_gen4_5,google_veo3_1

# Text output only
python -m src.main ./video.mp4 --format txt

# Dry run with verbose
python -m src.main ./video.mp4 --dry-run --verbose

# Custom output
python -m src.main ./video.mp4 --output-dir my_results --format json

# Use a specific Gemini model with rate limit
python -m src.main ./video.mp4 --gemini-model gemini-3.5-flash --rate-limit-rpm 1

# Mock mode (no API calls)
python -m src.main ./video.mp4 --mock

# Help
python -m src.main --help
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Required for Gemini API |
| `OPENAI_API_KEY` | Optional: fallback synthesis when Gemini unavailable |
| `GROQ_API_KEY` | Optional: Whisper transcription via Groq API (`whisper-large-v3`) |
| `VIDEO_REV_OUTPUT_DIR` | Default output directory |
| `VIDEO_REV_CONFIG_DIR` | Config directory path |
| `VIDEO_REV_LOG_LEVEL` | Log level override |
