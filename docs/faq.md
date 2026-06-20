# FAQ

## General

### What is VideoReverse?

VideoReverse deconstructs any video into a universal blueprint, then generates model-specific prompts for 8+ video AI models (Runway, Veo, Kling, Sora, Luma, Pika, Haiper, SVD).

### How much does it cost?

- **Gemini API**: ~$0.001/second of video (with compression and frame capping)
- **Mock mode**: Free (no API calls)
- **Free fallbacks**: OpenRouter and NVIDIA NIM have free tiers

### Do I need an API key?

Yes, for `GEMINI_API_KEY` (primary analysis). Use `--mock` mode to test without any API key.

## Installation

### `pip install vidrev` fails

Make sure you have Python 3.12+ installed:
```bash
python --version  # Should be 3.12 or higher
```

### ffmpeg not found

Install ffmpeg:
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### Docker build fails

Make sure Docker is running and you have enough disk space (2GB+ recommended).

## Usage

### Video is too long

Use smart sampling to reduce cost:
```bash
# Clip first 30 seconds
python -m src.main ./video.mp4 --sample-mode first-n --max-duration 30

# Extract 30s of highlights
python -m src.main ./video.mp4 --sample-mode highlights --max-duration 30
```

### Gemini rate limited (429/503)

The pipeline has automatic fallback:
1. Waits and retries
2. Falls back to lighter Gemini models
3. Falls back to OpenAI/OpenRouter/NVIDIA

Or reduce RPM:
```bash
python -m src.main ./video.mp4 --rate-limit-rpm 3
```

### Blueprint validation fails

This usually means the AI returned malformed JSON. The pipeline auto-sanitizes, but you can retry:
```bash
python -m src.main ./video.mp4 --max-retries 3
```

### How do I use the output?

1. Open the `.txt` file in `output_blueprints/`
2. Find the model section (e.g., "Runway Gen-4.5")
3. Copy the prompt text for each shot
4. Paste into your video AI generator
5. Generate each shot separately, combine in a video editor

## Web UI

### Web UI won't start

Check if port 7860 is in use:
```bash
lsof -i :7860  # Linux/macOS
netstat -ano | findstr :7860  # Windows
```

### Can't upload video via URL

Make sure `yt-dlp` is installed:
```bash
pip install yt-dlp
```

## Troubleshooting

### "No video path provided"

Specify a video file:
```bash
python -m src.main ./video.mp4
```

### "FFmpeg not found"

Install ffmpeg and ensure it's in your PATH.

### "Gemini API key missing"

Add your API key to `.env`:
```bash
echo "GEMINI_API_KEY=your_key_here" > .env
```

### Blueprint has 0 shots

The video may be too short or the analysis failed. Try:
```bash
python -m src.main ./video.mp4 --mock  # Test with mock data
```

### Output is empty

Check if the video file exists and is readable:
```bash
ls -la ./video.mp4
ffprobe ./video.mp4  # Should show video info
```

## Getting Help

- Check [GitHub Issues](https://github.com/Venkata-Manoj/videoreverse/issues)
- Read the [CLI Reference](cli-reference.md)
- See the [Architecture](architecture.md) docs
