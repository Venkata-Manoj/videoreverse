# VideoReverse — Agent Notes

## What This Is

Video-to-prompt pipeline that deconstructs any video into a universal blueprint, then generates model-specific prompts for 8+ video AI models (Runway, Veo, Kling, Sora, Luma, Pika, Haiper, SVD).

## Prerequisites

- **Python 3.12+** required. Use `pyenv install 3.12` if needed.
- `ffmpeg` for smart sampling and video analysis.
- `GEMINI_API_KEY` in `.env` file — for primary blueprint synthesis via Gemini File API.
- `OPENAI_API_KEY` (optional) in `.env` file — for automatic fallback when Gemini is unavailable.
- `OPENROUTER_API_KEY` (optional) in `.env` file — free fallback via Kimi K2.6 (text-only, 1 frame).
- `NVIDIA_NIM_API_KEY` (optional) in `.env` file — free fallback via Nemotron Nano VL 8B (multi-image vision).
- `openai-whisper` is installed from `requirements.txt` for local transcription during ingest.
- **Groq Whisper API** is the primary transcription backend — if `GROQ_API_KEY` is set in `.env`, it uses `whisper-large-v3` via Groq's OpenAI-compatible API. Falls back to local Whisper automatically if Groq is unavailable or no key is set.

## Docker

```bash
# CLI pipeline
docker compose run --rm vidrev src.main <video>
# Web UI
docker compose up -d vidrev-web
# Open http://localhost:7860
```

## Migration

```bash
# Show pending migrations
python scripts/migrate.py --list
# Apply all pending
python scripts/migrate.py
# Apply up to a specific version
python scripts/migrate.py --target 1
```

## Commands

- `python -m src.main <path_or_url>` — full pipeline: ingest → synthesize → compile → export
- `python -m src.ingest <path_or_url>` — standalone ingestion (metadata + frames)
- `python -m web` — local Web UI for testing (upload queue, downloads, prompt copy)
- `vidrev-web` — same as `python -m web` (after editable install)
- Paths auto-convert: Windows `E:\vidrev\test.mp4` → WSL `/mnt/e/vidrev/test.mp4`

- `python scripts/verify_output.py <video_name>` - verify latest saved JSON/TXT output without rerunning pipeline
- `python scripts/lint.py` — Run linter
- `python scripts/validate.py` — Validate outputs

## Architecture

```text
src/
├── main.py             ← CLI entry point
├── pipeline.py         ← Main orchestrator (chains all modules)
├── ingest.py           ← ffmpeg → metadata, frames, audio mood
├── synthesize.py       ← Gemini File API + responseSchema → blueprint
├── synthesize_openai.py ← OpenAI vision fallback (GPT-4o mini, auto-triggered)
├── synthesize_free_api.py ← Free API fallback (OpenRouter Kimi K2.6 + NVIDIA Nemotron VL 8B)
├── compile.py          ← Config-driven prompt compiler
├── export.py           ← JSON → human-readable .txt format
├── blueprint_prompt.py ← Shared system prompt + JSON schema
└── path_resolver.py    ← Path normalization utility

config/
├── prompt_templates.json ← Template registry (8 video models)
└── model_limits.json     ← Per-model free tier limits (RPM/TPM/RPD)

schemas/
└── blueprint.py   ← Pydantic V2 models: UniversalBlueprint, ChronologicalShot, GlobalAesthetic, etc.

utils/
├── validation.py    ← Blueprint validator (Pydantic V2 backed)
├── retry.py         ← Retry logic + exponential backoff
├── rate_limiter.py  ← Per-model RPM/TPM/RPD sliding window rate limiter
├── logger.py        ← Error logging
├── cli.py           ← CLI argument parser
├── video_type.py    ← Video type detection
├── cache.py         ← Blueprint caching
└── sampler.py       ← Smart frame sampling (ffmpeg clip + highlights)

web/
├── app.py            ← Flask server (upload + SSE progress)
├── jobs.py           ← DB-backed JobManager
├── db.py             ← SQLite + WAL persistence layer (jobs + job_events tables)
└── static/           ← HTML/CSS/JS UI (step timeline + results tabs)
```

**Flow:** Video → [sampler] → ffmpeg (metadata + audio) → Gemini (primary) → Gemini fallback chain (lighter models) → OpenAI (fallback 1) → OpenRouter Kimi K2.6 (fallback 2) → NVIDIA Nemotron VL 8B (fallback 3) → template compiler → dual output

**Persistence:** Job state and events persisted to `.cache/videoreverse.db` (SQLite + WAL). Auto-cleanup of jobs older than 24h. Override with `VIDEO_REV_DB_PATH` env var.

**Web UI Features:**

- **URL Input** — Paste any video URL (YouTube, Vimeo, direct `.mp4`, etc.) — downloads via `yt-dlp` automatically
- **Job History** — Previous jobs saved to localStorage, re-run with same settings
- **Template Editor** — In-browser template customization with save back to disk

**Universal Schema:** `{ global_aesthetic, chronological_shots[] }` — enforced via `responseSchema` generated dynamically from Pydantic V2 `UniversalBlueprint.model_json_schema()`

## Key Files

- `src/main.py` — CLI entry point. Use `python -m src.main --help` for options.
- `src/pipeline.py` — Orchestrator. Accepts any video path/URL. Saves to `output_blueprints/`.
- `src/synthesize.py` — Uses Gemini File API (default) or frames-only inline images (with `--frames-only`). Cleans up after analysis.
- `src/synthesize_free_api.py` — Free fallback backends (OpenRouter + NVIDIA NIM).
- `schemas/blueprint.py` — Pydantic V2 models for UniversalBlueprint, used by validation and responseSchema generation.
- `config/prompt_templates.json` — Add new models here. Each entry: `label`, `template` (placeholders: `{camera}`, `{framing}`, `{style}`, `{action}`, `{environment}`, `{lighting}`, `{color_grading}`, `{duration}`, `{negative}`, `{aspect_ratio}`), `supports_negative`, `max_duration`, `aspect_ratio_support`, `enhancement_rules`.
- `config/model_limits.json` — Per-model free tier limits (RPM, TPM, RPD). Used by `utils/rate_limiter.py` to enforce quotas.
- `utils/rate_limiter.py` — Sliding window rate limiter enforcing RPM/TPM/RPD per model before API calls.

## CLI Options

```bash
python -m src.main <video> [options]

Options:
  --model, -m          Specific models (comma-separated, 10 available)
  --output-dir, -o     Output directory
  --format             json, txt, both, none
  --verbose, -v        Debug logging
  --dry-run            Output without saving
  --force, -F          Skip failed steps
  --max-retries, -r    API retry attempts (default: 2)
  --max-frames         Max frames to extract (default: 60, reduces token usage)
  --max-duration       Pre-clip video to first N seconds
  --sample-mode        Sampling: full, first-n, highlights (requires ffmpeg)
  --video-type         Override auto-detected video type
  --no-compress        Skip video compression before API upload
  --compress-width     Target width for compression (default: 720, min: 360)
  --no-cache           Disable blueprint caching
  --no-transcribe      Skip local Whisper transcription
  --wsl                Force WSL path conversion
  --win                Force Windows path mode
  --gemini-model       Gemini model: gemini-2.5-flash, gemini-2.5-flash-lite, gemini-3.5-flash, gemini-3.1-flash-lite, gemini-3-flash, gemini-flash-latest, gemini-flash-lite-latest
  --rate-limit-rpm     Max API requests per minute (default: 5 for free tier)
  --frames-only        Send extracted frames as inline images instead of full video upload.
                        Token cost bounded by --max-frames regardless of duration. No 429/503
                        from large uploads. Use for long videos to avoid rate limits.
  --no-file-api         Alias for --frames-only
  --blur-threshold FLOAT  Minimum sharpness score (Laplacian variance normalized).
                            Higher = stricter. Default 100 works for 720p-4K.
                            Set 0 to disable. High-motion frames always preserved.
  --mock               Skip API calls, generate synthetic blueprint from metadata
  --help, -h           Show help
```

## Resource Optimizations

### Video Compression (auto-enabled)
Videos wider than 720px are compressed before Gemini upload via ffmpeg (scaled to 720p, CRF 28, AAC 64k audio). Reduces upload size by 60-90% with no quality loss for AI analysis. Skip with `--no-compress`, adjust with `--compress-width 480`.

### Frame Capping (default: 60)
After extracting all I-frames, the list is downsampled to `--max-frames` (default 60) using uniform sampling. This reduces prompt token count and API cost. The frame timeline in the blueprint covers the full duration.

### Upload Caching (automatic)
If Gemini returns a retriable error (503/429), the uploaded file URI is cached in memory and reused on retry — no re-upload waste. The file is cleaned up on success.

### Default Retries Reduced (2 instead of 3)
Combined with upload caching, 2 retries are sufficient.

### Smart Sampling
Reduces API cost by 50-90% for long videos.

- `--sample-mode first-n --max-duration 30` → clip first 30s
- `--sample-mode highlights --max-duration 30` → extract 30s of highest-motion segments
- Cost estimate: ~$0.001/second for Gemini 2.5 Flash

### Frame Blur Filtering (optional, requires opencv-python-headless)
After I-frame extraction, each frame is scored for sharpness using Laplacian variance
(normalized by resolution). Frames below --blur-threshold (default 100) are dropped
unless they have high motion level (motion blur is intentional). Falls back gracefully
if opencv-python-headless is not installed.

**OpenCV Import Latency:** The first `import cv2` incurs ~200–500ms cold-start overhead
(due to native library loading). This is a one-time cost per process — subsequent
imports are instant. No impact on pipeline throughput for batch processing.

### Aggressive Blur Filter (optional, --aggressive-blur-filter)
When enabled, also drops blurry-high-motion frames where both adjacent frames are sharp.
These are typically transient pan/zoom artifacts — intentional camera movement that
creates a momentary blur. Only meaningful with --blur-threshold (default 100).

## Error Codes

| Code | Description |
|------|-------------|
| VR-001 | No video path provided |
| VR-002 | Unsupported model |
| VR-003 | Invalid CLI argument |
| VR-004 | File not found |
| VR-005 | Path resolution failed |
| VR-006 | URL download failed |
| VR-101 | FFmpeg not found |
| VR-102 | FFprobe metadata failed |
| VR-103 | Frame extraction failed |
| VR-104 | Audio extraction failed |
| VR-105 | Whisper transcription failed |
| VR-106 | Smart sampling failed |
| VR-107 | Video corrupt |
| VR-201 | Gemini API key missing |
| VR-202 | Gemini File upload failed |
| VR-203 | Gemini synthesis failed |
| VR-204 | Gemini rate limited |
| VR-205 | Gemini service down |
| VR-301 | Prompt compilation failed |
| VR-302 | Blueprint validation failed |
| VR-402 | Output write failed |
| VR-499 | Internal error |

## Error Handling

1. **Retry with backoff** — 3 attempts, exponential delay
2. **Validation** — Sanitize malformed JSON automatically (handles missing `shot_index`, string `negative_elements`, etc.)
3. **Logging** — Errors persisted to `output_blueprints/errors.log`

## Gotchas

- **WSL-native pipeline.** Run from WSL. Windows paths auto-convert.
- **ffmpeg output can be large** — subprocess handles large output automatically.
- **Gemini File API uploads full video** — large files cost more tokens.
- **Uploaded files deleted** after blueprint generation.
- **Pydantic V2** is the core validation layer in `schemas/blueprint.py`. Used by `utils/validation.py` and `src/synthesize.py` for responseSchema generation.
- **Automatic fallback** — Gemini → OpenAI → OpenRouter Kimi K2.6 → NVIDIA Nemotron Nano VL 8B
- **Remote URLs may return HTTP 403** — use local files for testing.
- **Output persists** as dual format: `.json` + `.txt`
- **Job state persists** in `.cache/videoreverse.db` (SQLite + WAL). Override path with `VIDEO_REV_DB_PATH`.

## Adding a New Model

1. Edit `config/prompt_templates.json` with: `label`, `template` (placeholders: `{camera}`, `{framing}`, `{style}`, `{action}`, `{environment}`, `{lighting}`, `{color_grading}`, `{duration}`, `{negative}`, `{aspect_ratio}`), `supports_negative`, `max_duration`, `aspect_ratio_support`, `enhancement_rules`.
2. That's it. `compile.py` reads the config dynamically.

## Testing

```bash
python -m pytest tests/unit/   # Run all unit tests
python scripts/lint.py         # Run linter
python scripts/validate.py     # Validate outputs
```

## Testing Matrix

Keep diverse test videos:

- `test1.mp4` — CGI/animation
- `test_drone.mp4` — aerial footage
- `test_anime.mp4` — 2D animation
- `test_vlog.mp4` — handheld multi-cut

## Do's

- always commit the project when a new feature is added and tested successfully without explicitly mentioned by user
- always ask user to commit this feature/something and get it tested before moving forward
- make the commit message very clear and concise
- when you are done with all the tasks user mentioned then ask user to commit the changes and move forward
- always check TODO.md for any pending tasks and remind user about it if there are any.
- always test the code and get it tested before moving forward.
- if a task or feature request feels overengineered for a single-local-user tool (e.g., K8s, microservices, multi-tenancy, queues, distributed caching, auth, webhooks, observability stacks, API marketplaces), call it out and suggest a simpler alternative before implementing.

## Update/Enhance

- keep the prompts updated and enhanced
- always enhance the prompts based on the new features added
- always test the prompts and get the best results possible
- if you think the prompts can be enhanced further then enhance them
- update AGENTS.md with the changes made
- don't push the code to github, just commit the changes. I personally push the code (just notify me when you commit)

## Dont's

- dont test the code and then commit without asking user to commit
