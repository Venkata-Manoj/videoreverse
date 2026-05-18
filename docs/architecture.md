# VideoReverse — Architecture

## Overview

VideoReverse is a modular pipeline that deconstructs videos into production blueprints, then compiles model-specific prompts.

## Pipeline Flow

```
┌─────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌────────┐
│  Video  │───▶│  Ingest  │───▶│ Synthesize │───▶│ Compile  │───▶│ Export │
└─────────┘    └──────────┘    └───────────┘    └──────────┘    └────────┘
                    │                 │               │              │
               peepshow           Gemini           config       .json
               metadata            File API      templates     .txt
```

## Modules

### src/ingest.js
Extracts video metadata using peepshow CLI:
- Duration, resolution, FPS, codec
- Audio analysis with mood detection
- Motion signal level
- Frame extraction

### src/synthesize.js
Analyzes video using Gemini File API:
- Uploads video for multimodal analysis
- Enforces JSON schema via responseSchema
- Cleans up uploaded files
- Includes audio context in prompts

### src/compile.js
Compiles prompts from blueprint + templates:
- Config-driven model templates
- Shot-by-shot prompt generation
- Negative prompt support
- Aspect ratio handling

### src/export.js
Formats output for human consumption:
- JSON (machine-readable)
- TXT (copy-paste ready)

## Utilities

| Module | Purpose |
|--------|---------|
| `utils/validation.js` | Blueprint JSON validation |
| `utils/retry.js` | Exponential backoff for API calls |
| `utils/fallback.js` | Graceful degradation on failure |
| `utils/logger.js` | Structured logging + error tracking |
| `utils/cli.js` | CLI argument parsing |
| `utils/cache.js` | Blueprint caching |
| `utils/compare.js` | Prompt diff tool |

## Data Flow

```javascript
// Pipeline output structure
{
  video_metadata: { ... },
  blueprint: {
    global_aesthetic: { art_style, color_grading, lighting_setup },
    chronological_shots: [
      { shot_index, duration_seconds, camera_direction, ... },
      ...
    ]
  },
  prompts: {
    runway_gen4_5: { label, shots: [...] },
    google_veo3_1: { label, shots: [...] },
    ...
  }
}
```

## Error Handling

1. **Retry with backoff** — 3 attempts, exponential delay
2. **Fallback mode** — Text-only prompts from metadata
3. **Validation** — Sanitize malformed JSON
4. **Logging** — Errors persisted to `output_blueprints/errors.log`