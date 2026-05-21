# VideoReverse — Architecture

## Overview

VideoReverse is a modular pipeline that deconstructs videos into production blueprints, then compiles model-specific prompts.

## Pipeline Flow

```
┌─────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌────────┐
│  Video  │───▶│  Ingest  │───▶│ Synthesize │───▶│ Compile  │───▶│ Export │
└─────────┘    └──────────┘    └───────────┘    └──────────┘    └────────┘
                     │                 │               │              │
                  ffmpeg           Gemini           config       .json
                  metadata          File API      templates     .txt
```

## Modules

### src/ingest.py
Extracts video metadata using ffmpeg:
- Duration, resolution, FPS, codec
- Audio analysis with mood detection
- Motion signal level
- Frame extraction

### src/synthesize.py
Analyzes video using Gemini File API:
- Uploads video for multimodal analysis
- Enforces JSON schema via responseSchema
- Cleans up uploaded files
- Includes audio context in prompts

### src/compile.py
Compiles prompts from blueprint + templates:
- Config-driven model templates
- Shot-by-shot prompt generation
- Negative prompt support
- Aspect ratio handling

### src/export.py
Formats output for human consumption:
- JSON (machine-readable)
- TXT (copy-paste ready)

## Utilities

| Module | Purpose |
|--------|---------|
| `utils/validation.py` | Blueprint JSON validation |
| `utils/retry.py` | Exponential backoff for API calls |
| `utils/fallback.py` | Graceful degradation on failure |
| `utils/logger.py` | Structured logging + error tracking |
| `utils/cli.py` | CLI argument parsing |
| `utils/cache.py` | Blueprint caching |
| `utils/compare.py` | Prompt diff tool |

## Data Flow

```python
# Pipeline output structure
{
  "video_metadata": { ... },
  "blueprint": {
    "global_aesthetic": { "art_style": "...", "color_grading": "...", "lighting_setup": "..." },
    "chronological_shots": [
      { "shot_index": 0, "duration_seconds": 5.0, "camera_direction": "...", ... },
      ...
    ]
  },
  "prompts": {
    "runway_gen4_5": { "label": "...", "shots": [...] },
    "google_veo3_1": { "label": "...", "shots": [...] },
    ...
  }
}
```

## Error Handling

1. **Retry with backoff** — 3 attempts, exponential delay
2. **Fallback mode** — Text-only prompts from metadata
3. **Validation** — Sanitize malformed JSON
4. **Logging** — Errors persisted to `output_blueprints/errors.log`
