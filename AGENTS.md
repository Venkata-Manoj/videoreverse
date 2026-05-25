# VideoReverse — Agent Notes

## What This Is

Video-to-prompt pipeline that deconstructs any video into a universal blueprint, then generates model-specific prompts for 8+ video AI models (Runway, Veo, Kling, Sora, Luma, Pika, Haiper, SVD).

## Prerequisites

- **Python 3.12+** required. Use `pyenv install 3.12` if needed.
- `ffmpeg` for smart sampling and video analysis.
- `GEMINI_API_KEY` in `.env` file — for blueprint synthesis via Gemini File API.
- `openai-whisper` is installed from `requirements.txt` for local transcription during ingest.

## Commands

- `python -m src.main <path_or_url>` — full pipeline: ingest → synthesize → compile → export
- `python -m src.main --batch <dir_or_file>` — batch process multiple videos
- `python -m src.ingest <path_or_url>` — standalone ingestion (metadata + frames)
- `python -m benchmark` — run prompt quality benchmarks
- `python -m web` — local Web UI for non-CLI testing (upload queue, downloads, prompt copy)
- `vidrev-web` — same as `python -m web` (after editable install)
- Paths auto-convert: Windows `E:\vidrev\test.mp4` → WSL `/mnt/e/vidrev/test.mp4`

- `python scripts/verify_output.py <video_name>` - verify latest saved JSON/TXT output without rerunning pipeline

## Architecture

```text
src/
├── main.py             ← CLI entry point
├── pipeline.py         ← Main orchestrator (chains all modules)
├── batch.py            ← Multi-video batch processor (parallel + resume)
├── ingest.py           ← ffmpeg → metadata, frames, audio mood
├── synthesize.py       ← Gemini File API + responseSchema → blueprint
├── compile.py          ← Config-driven prompt compiler
├── export.py           ← JSON → human-readable .txt format
├── blueprint_prompt.py ← Shared system prompt + JSON schema
└── path_resolver.py    ← Path normalization utility

config/
└── prompt_templates.json ← Template registry (8 video models)

utils/
├── validation.py    ← Blueprint validator
├── retry.py         ← Retry logic + exponential backoff
├── fallback.py      ← Graceful degradation
├── logger.py        ← Error logging
├── cli.py           ← CLI argument parser
├── video_type.py    ← Video type detection
├── cache.py         ← Blueprint caching
├── compare.py       ← Prompt comparison
└── sampler.py       ← Smart frame sampling (ffmpeg clip + highlights)

benchmark/
├── benchmark.py      ← Prompt quality benchmark runner
└── metrics.py        ← Quality metrics (shot count, style, action, etc.)

web/
├── app.py            ← Flask server (upload + SSE progress)
├── jobs.py           ← Background job runner
└── static/           ← HTML/CSS/JS UI (step timeline + results tabs)
```

**Flow:** Video → [sampler] → ffmpeg (metadata + audio) → Gemini File API (multimodal analysis) → template compiler → dual output

**Web UI Features:**

- **Job History** — Previous jobs saved to localStorage, re-run with same settings
- **Comparison Tool** — Side-by-side blueprint/prompt diff of any two jobs
- **Template Editor** — In-browser template customization with save back to disk
- **Monitoring Dashboard** — API usage stats, timing metrics, error/fallback rates
- **Configuration Profiles** — Fast/Quality/Cheap presets with custom save/load
- **Accessibility** — Skip links, ARIA labels, keyboard navigation, focus-visible outlines
- **Web Worker** — Offloads JSON formatting from main thread

**Universal Schema:** `{ global_aesthetic, chronological_shots[] }` — enforced via `responseSchema`

## Key Files

- `src/main.py` — CLI entry point. Use `python -m src.main --help` for options.
- `src/pipeline.py` — Orchestrator. Accepts any video path/URL. Saves to `output_blueprints/`.
- `src/synthesize.py` — Uses Gemini File API. Cleans up after analysis.
- `config/prompt_templates.json` — Add new models here. Each entry: `label`, `template`, `supports_negative`, `max_duration`, `aspect_ratio_support`.

## CLI Options

```bash
python -m src.main <video> [options]

Options:
  --model, -m          Specific models (comma-separated)
  --output-dir, -o     Output directory
  --format             json, txt, both, none
  --verbose, -v        Debug logging
  --dry-run            Output without saving
  --force, -F          Skip failed steps
  --max-retries, -r    API retry attempts (default: 3)
  --max-duration       Pre-clip video to first N seconds
  --sample-mode        Sampling: full, first-n, highlights (requires ffmpeg)
  --video-type         Override auto-detected video type
  --no-cache           Disable blueprint caching
  --no-transcribe      Skip local Whisper transcription
  --interactive, -i    Open REPL after pipeline for iterative prompt tuning
  --wsl                Force WSL path conversion
  --win                Force Windows path mode
  --gemini-model       Gemini model: gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash
  --batch <file|dir>   Process all videos in a directory or file list
  --parallel <N>       Max concurrent videos in batch mode (default: 4)
  --help, -h           Show help
```

**Smart Sampling:** Reduces API cost by 50-90% for long videos.

- `--sample-mode first-n --max-duration 30` → clip first 30s
- `--sample-mode highlights --max-duration 30` → extract 30s of highest-motion segments
- Cost estimate: ~$0.001/second for Gemini 2.5 Flash

## Error Codes

All errors use standardized **VR-XXX** codes. Use `--explain-error <CODE>` for troubleshooting.

| Code | Description |
|------|-------------|
| VR-001 | No video path provided |
| VR-002 | Unsupported model |
| VR-003 | Invalid CLI argument |
| VR-004 | File not found |
| VR-005 | Path resolution failed |
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
| VR-303 | Fallback activated |
| VR-402 | Output write failed |
| VR-499 | Internal error |

## Error Handling

1. **Retry with backoff** — 3 attempts, exponential delay
2. **Fallback mode** — Text-only prompts from metadata if Gemini fails
3. **Validation** — Sanitize malformed JSON automatically
4. **Logging** — Errors persisted to `output_blueprints/errors.log`
5. **Error Codes** — All errors have standardized VR-XXX codes with troubleshooting steps

## Gotchas

- **WSL-native pipeline.** Run from WSL. Windows paths auto-convert.
- **ffmpeg output can be large** — subprocess handles large output automatically.
- **Gemini File API uploads full video** — large files cost more tokens.
- **Uploaded files deleted** after blueprint generation.
- **No external validation library** — lightweight custom validation.
- **Remote URLs may return HTTP 403** — use local files for testing.
- **Output persists** as dual format: `.json` + `.txt`

## Adding a New Model

1. Edit `config/prompt_templates.json` with: `label`, `template` (placeholders: `{camera}`, `{framing}`, `{style}`, `{action}`, `{environment}`, `{lighting}`, `{color_grading}`, `{duration}`, `{negative}`, `{aspect_ratio}`), `supports_negative`, `max_duration`, `aspect_ratio_support`, `enhancement_rules`.
2. That's it. `compile.py` reads the config dynamically.

**Enhancement Rules Structure:**

```json
{
  "enhancement_rules": {
    "preferred_order": ["camera", "framing", "style", "action", "environment", "lighting"],
    "keyword_injection": {
      "camera_keywords": ["35mm lens", "50mm lens", "f/2.8"],
      "style_keywords": ["cinematic", "photorealistic"],
      "action_keywords": ["smooth motion", "natural physics"]
    },
    "prompt_guidelines": {
      "max_length": 300,
      "sentence_style": "concise",
      "avoid_adjectives": ["stunning", "breathtaking"],
      "prefer_specifics": ["50mm lens", "f/2.8", "shallow depth of field"]
    }
  }
}
```

## Testing

```bash
python -m src.run_tests        # Run full test suite
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

- always commit the project when a new frature is added and tested successfully without explicitly mentioned by user
- always ask user to commit this feature/something and get it tested before moving forward
- make the commit message very clear and concise
- when you are done with all the tasks user mentioned then ask user to commit the changes and move forward
- always check TODO.md for any pending tasks and remain user about it if there are any.
- always test the code and get it tested before moving forward.

## Update/Enhance

- keep the prompts updated and enhanced
- always enhance the prompts based on the new features added
- always test the prompts and get the best results possible
- if you think the prompts can be enhanced further then enhance them
- update AGENTS.md with the changes made
- don't push the code to github, just commit the changes. I personally push the code (just notify me when you commit)

## Dont's

- dont test the code and then commit without asking user to commit
