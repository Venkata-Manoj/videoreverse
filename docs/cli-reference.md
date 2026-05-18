# VideoReverse — CLI Reference

## Commands

### Main Pipeline
```bash
node src/main.js <video_path_or_url> [options]
```

### Individual Modules
```bash
node src/pipeline.js <video>      # Full pipeline
node src/ingest.js <video>        # Ingestion only
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
| `--max-retries, -r` | API retry attempts | `3` |
| `--max-duration` | Pre-clip to N seconds | - |
| `--video-type` | Override video type detection | Auto |
| `--no-cache` | Disable blueprint caching | `false` |
| `--wsl` | Force WSL path mode | Auto |
| `--win` | Force Windows path mode | Auto |

## Examples

```bash
# Basic usage
node src/main.js ./video.mp4

# Specific models
node src/main.js ./video.mp4 --model runway_gen4_5,google_veo3_1

# Text output only
node src/main.js ./video.mp4 --format txt

# Dry run with verbose
node src/main.js ./video.mp4 --dry-run --verbose

# Custom output
node src/main.js ./video.mp4 --output-dir my_results --format json

# Help
node src/main.js --help
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Required for Gemini API |
| `VIDEO_REV_OUTPUT_DIR` | Default output directory |
| `VIDEO_REV_CONFIG_DIR` | Config directory path |
| `VIDEO_REV_LOG_LEVEL` | Log level override |