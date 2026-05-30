from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.pipeline import run_pipeline
from utils.error_codes import VRError


@pytest.fixture
def base_options() -> dict:
    return {
        "video_path": "/mnt/e/vidrev/test1.mp4",
        "models": None,
        "output_dir": "/tmp/test_output",
        "format": "none",
        "dry_run": True,
        "max_retries": 1,
        "max_duration": None,
        "sample_mode": "full",
        "video_type": None,
        "no_cache": True,
        "no_transcribe": True,
        "wsl_mode": None,
        "gemini_model": "gemini-2.5-flash",
    }


SAMPLE_RESULT = {
    "path": "/tmp/sampled/clipped.mp4",
    "temp_dir": "/tmp/sampled",
    "mode": "first-n",
    "duration": 30,
    "size_bytes": 1024000,
}

INGEST_RESULT = {
    "video_metadata": {
        "filename": "test1.mp4",
        "source_path": "/tmp/sampled/clipped.mp4",
        "duration_seconds": 30.0,
        "width": 1920,
        "height": 1080,
        "dimensions": "1920x1080",
        "aspect_ratio": "16:9",
        "fps": 30.0,
        "codec": "h264",
        "container": "mp4",
        "bitrate_kbps": 5000,
    },
    "audio_data": {"has_audio": False},
    "extraction": {
        "strategy": "ffmpeg_keyframes",
        "motion_signal_level": "medium",
        "frames_emitted": 10,
        "frames_deduped": 10,
        "elapsed_ms": 100,
    },
    "timeline_frames": [
        {"index": 0, "bytes": 50000, "timestamp_seconds": 0.0, "motion_level": "medium", "frame_hash": "abc"},
    ],
    "scene_changes": [],
    "output_dir": "/tmp/ingest_temp",
}

BLUEPRINT_RESULT = {
    "global_aesthetic": {"style": "cinematic", "color_grading": "cool", "lighting": "natural"},
    "chronological_shots": [
        {
            "start_time_seconds": 0.0,
            "end_time_seconds": 10.0,
            "camera": "static",
            "framing": "wide",
            "style": "cinematic",
            "action": "scene opens",
            "environment": "outdoor",
            "lighting": "natural",
            "color_grading": "cool",
            "duration": 10.0,
            "negative": "blur",
            "frame_references": [{"frame_index": 0, "relevance": "key_frame"}],
        }
    ],
}


@pytest.mark.anyio
async def test_pipeline_calls_sample_video_and_passes_path(base_options: dict) -> None:
    options = {**base_options, "sample_mode": "first-n", "max_duration": 30}

    with (
        patch("src.pipeline.sample_video", return_value=SAMPLE_RESULT) as mock_sample,
        patch("src.pipeline.cleanup_sample") as mock_cleanup,
        patch("src.pipeline.ingest_video", return_value=INGEST_RESULT) as mock_ingest,
        patch("src.pipeline.build_blueprint", new_callable=AsyncMock, return_value=BLUEPRINT_RESULT) as mock_build,
        patch("src.pipeline.compile_prompts", return_value={}) as mock_compile,
    ):
        output = await run_pipeline(options)

        mock_sample.assert_called_once_with(options["video_path"], options)
        mock_ingest.assert_called_once()
        assert mock_ingest.call_args[0][0] == SAMPLE_RESULT["path"]
        mock_build.assert_called_once()
        assert mock_build.call_args[0][0] == SAMPLE_RESULT["path"]
        mock_cleanup.assert_called_once_with(SAMPLE_RESULT)
        assert output["_meta"]["sampling"] == SAMPLE_RESULT


@pytest.mark.anyio
async def test_pipeline_raises_on_sampling_failure_in_highlights_mode(base_options: dict) -> None:
    options = {**base_options, "sample_mode": "highlights"}

    with (
        patch("src.pipeline.sample_video", side_effect=RuntimeError("ffmpeg not found")) as mock_sample,
    ):
        with pytest.raises(VRError, match="VR-106"):
            await run_pipeline(options)

        mock_sample.assert_called_once_with(options["video_path"], options)


@pytest.mark.anyio
async def test_pipeline_falls_back_on_sampling_failure_with_force(base_options: dict) -> None:
    options = {**base_options, "sample_mode": "highlights", "force": True}

    with (
        patch("src.pipeline.sample_video", side_effect=RuntimeError("ffmpeg not found")) as mock_sample,
        patch("src.pipeline.cleanup_sample") as mock_cleanup,
        patch("src.pipeline.ingest_video", return_value=INGEST_RESULT) as mock_ingest,
        patch("src.pipeline.build_blueprint", new_callable=AsyncMock, return_value=BLUEPRINT_RESULT) as mock_build,
        patch("src.pipeline.compile_prompts", return_value={}) as mock_compile,
    ):
        output = await run_pipeline(options)

        mock_sample.assert_called_once_with(options["video_path"], options)
        mock_ingest.assert_called_once()
        assert mock_ingest.call_args[0][0] == options["video_path"]
        mock_build.assert_called_once()
        assert mock_build.call_args[0][0] == options["video_path"]
        mock_cleanup.assert_called_once_with(None)
        assert output["_meta"]["sampling"] is None


@pytest.mark.anyio
async def test_pipeline_full_mode_passes_original_path(base_options: dict) -> None:
    options = {**base_options, "sample_mode": "full"}

    with (
        patch("src.pipeline.sample_video", return_value=SAMPLE_RESULT) as mock_sample,
        patch("src.pipeline.cleanup_sample") as mock_cleanup,
        patch("src.pipeline.ingest_video", return_value=INGEST_RESULT) as mock_ingest,
        patch("src.pipeline.build_blueprint", new_callable=AsyncMock, return_value=BLUEPRINT_RESULT) as mock_build,
        patch("src.pipeline.compile_prompts", return_value={}) as mock_compile,
    ):
        output = await run_pipeline(options)

        mock_sample.assert_called_once()
        mock_ingest.assert_called_once()
        assert mock_ingest.call_args[0][0] == SAMPLE_RESULT["path"]
        assert output["_meta"]["sampling"] == SAMPLE_RESULT


@pytest.mark.anyio
async def test_pipeline_passes_frames_only_option(base_options: dict) -> None:
    options = {**base_options, "frames_only": True}

    with (
        patch("src.pipeline.sample_video", return_value=SAMPLE_RESULT) as mock_sample,
        patch("src.pipeline.cleanup_sample") as mock_cleanup,
        patch("src.pipeline.ingest_video", return_value=INGEST_RESULT) as mock_ingest,
        patch("src.pipeline.build_blueprint", new_callable=AsyncMock, return_value=BLUEPRINT_RESULT) as mock_build,
        patch("src.pipeline.compile_prompts", return_value={}) as mock_compile,
    ):
        output = await run_pipeline(options)

        mock_build.assert_called_once()
        _call_options = mock_build.call_args[0][2]
        assert _call_options.get("frames_only") is True
