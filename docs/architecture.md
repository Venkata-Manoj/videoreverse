# VideoReverse — Architecture

## Overview

VideoReverse is a modular pipeline that deconstructs videos into production blueprints, then compiles model-specific prompts. The Web UI adds an optional download step before ingest for remote URLs.

## Pipeline Flow

```
┌──────────┐   ┌─────────┐    ┌──────────┐    ┌─────────────────┐    ┌──────────┐    ┌────────┐
│  Download│──▶│  Video  │───▶│  Ingest  │───▶│   Synthesize    │───▶│ Compile  │───▶│ Export │
│ (yt-dlp) │   └─────────┘    └──────────┘    └────────┬────────┘    └──────────┘    └────────┘
└──────────┘                       │                    │                  │              │
   (Web UI only)             ffmpeg + Groq         fallback chain:    config          .json
                             Whisper API           gemini (primary)   templates       + .txt
                              + compression          → lighter Gemini
                              + frame capping        → OpenAI GPT-4o
                                                     → OpenRouter K2.6
                                                     → NVIDIA Nemotron
```

## Modules

### src/ingest.py
Extracts video metadata using ffmpeg:
- Duration, resolution, FPS, codec
- Audio analysis with mood detection
- Motion signal level
- Frame extraction
- Audio transcription via Groq Whisper API (`whisper-large-v3`) or local Whisper fallback

### src/synthesize.py
Analyzes video using Gemini File API:
- Uploads video for multimodal analysis (with in-memory upload caching for retries)
- Enforces JSON schema via responseSchema
- Rate-limited via `wait_for_capacity()` before each API call
- Falls back through lighter Gemini models automatically on failure
- Cleans up uploaded files only on success
- Includes audio context and frame timeline in prompts

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
| `utils/rate_limiter.py` | Sliding window RPM/TPM/RPD rate limiter |
| `utils/logger.py` | Structured logging + error tracking |
| `utils/cli.py` | CLI argument parsing |
| `utils/cache.py` | Blueprint caching |
| `utils/sampler.py` | Smart frame sampling |

### Configuration Files

| File | Purpose |
|------|---------|
| `config/prompt_templates.json` | Template registry for 10 video models |
| `config/model_limits.json` | Per-model free tier limits (RPM, TPM, RPD) |

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

1. **Retry with backoff** — 2 attempts, exponential delay + jitter (upload cache avoids re-upload on retry)
2. **Rate limiting** — `utils/rate_limiter.py` throttles per model RPM/TPM/RPD before API calls; waits and retries automatically
3. **Gemini fallback chain** — primary model → lighter Gemini models → OpenAI → OpenRouter → NVIDIA
4. **Validation** — Sanitize malformed JSON (handles missing `shot_index`, string `negative_elements`)
5. **Logging** — Errors persisted to `output_blueprints/errors.log`
