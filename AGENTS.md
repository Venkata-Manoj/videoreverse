# VideoReverse — Agent Notes

## What This Is

Video-to-prompt pipeline that deconstructs any video into a universal blueprint, then generates model-specific prompts for 8+ video AI models (Runway, Veo, Kling, Sora, Luma, Pika, Haiper, SVD).

## Prerequisites

- **Node.js 22+** required. Use `nvm install 22` if system Node is older.
- `peepshow` must be installed globally (`npm i -g peepshow`) — the core frame extraction engine.
- `GEMINI_API_KEY` in `.env` file — for blueprint synthesis via Gemini File API.

## Commands

- `node src/main.js <path_or_url>` — full pipeline: ingest → synthesize → compile → export
- `node src/ingest.js <path_or_url>` — standalone ingestion (metadata + frames)
- Paths auto-convert: Windows `E:\vidrev\test.mp4` → WSL `/mnt/e/vidrev/test.mp4`

## Architecture

```text
src/
├── main.js             ← CLI entry point
├── pipeline.js         ← Main orchestrator (chains all modules)
├── ingest.js           ← peepshow CLI → metadata, frames, audio mood
├── synthesize.js       ← Gemini File API + responseSchema → blueprint
├── compile.js          ← Config-driven prompt compiler
├── export.js           ← JSON → human-readable .txt format
├── blueprint_prompt.js ← Shared system prompt + JSON schema
└── path-resolver.js    ← Path normalization utility

config/
└── prompt_templates.json ← Template registry (8 video models)

utils/
├── validation.js    ← Blueprint validator
├── retry.js         ← Retry logic + exponential backoff
├── fallback.js      ← Graceful degradation
├── logger.js        ← Error logging
├── cli.js           ← CLI argument parser
├── video-type.js    ← Video type detection
├── cache.js         ← Blueprint caching
├── compare.js       ← Prompt comparison
└── sampler.js       ← Smart frame sampling (ffmpeg clip + highlights)
```

**Flow:** Video → [sampler] → peepshow (metadata + audio) → Gemini File API (multimodal analysis) → template compiler → dual output

**Universal Schema:** `{ global_aesthetic, chronological_shots[] }` — enforced via `responseSchema`

## Key Files

- `src/main.js` — CLI entry point. Use `node src/main.js --help` for options.
- `src/pipeline.js` — Orchestrator. Accepts any video path/URL. Saves to `output_blueprints/`.
- `src/synthesize.js` — Uses Gemini File API. Cleans up after analysis.
- `config/prompt_templates.json` — Add new models here. Each entry: `label`, `template`, `supports_negative`, `max_duration`, `aspect_ratio_support`.

## CLI Options

```bash
node src/main.js <video> [options]

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
  --wsl                Force WSL path conversion
  --win                Force Windows path mode
  --help, -h           Show help
```

**Smart Sampling:** Reduces API cost by 50-90% for long videos.
- `--sample-mode first-n --max-duration 30` → clip first 30s
- `--sample-mode highlights --max-duration 30` → extract 30s of highest-motion segments
- Cost estimate: ~$0.001/second for Gemini 2.5 Flash

## Error Handling

1. **Retry with backoff** — 3 attempts, exponential delay
2. **Fallback mode** — Text-only prompts from metadata if Gemini fails
3. **Validation** — Sanitize malformed JSON automatically
4. **Logging** — Errors persisted to `output_blueprints/errors.log`

## Gotchas

- **WSL-native pipeline.** Run from WSL. Windows paths auto-convert.
- **peepshow output can be large** — 10MB `maxBuffer` in ingest.
- **Gemini File API uploads full video** — large files cost more tokens.
- **Uploaded files deleted** after blueprint generation.
- **No Zod dependency** — lightweight custom validation.
- **Remote URLs may return HTTP 403** — use local files for testing.
- **Output persists** as dual format: `.json` + `.txt`

## Adding a New Model

1. Edit `config/prompt_templates.json` with: `label`, `template` (placeholders: `{camera}`, `{framing}`, `{style}`, `{action}`, `{environment}`, `{lighting}`, `{color_grading}`, `{duration}`, `{negative}`, `{aspect_ratio}`), `supports_negative`, `max_duration`, `aspect_ratio_support`, `enhancement_rules`.
2. That's it. `compile.js` reads the config dynamically.

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
npm test           # Run all tests
npm run lint       # Run linter
npm run validate   # Validate outputs
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

## Update/Enhance

- keep the prompts updated and enhanced
- always enhance the prompts based on the new features added
- always test the prompts and get the best results possible
- if you think the prompts can be enhanced further then enhance them
- update AGENTS.md with the changes made

## Dont's

- dont test the code and then commit without asking user to commit
