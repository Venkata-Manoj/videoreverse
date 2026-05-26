from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class FrameReference(BaseModel):
    """Reference to a specific frame that informed shot analysis."""
    model_config = ConfigDict(str_strip_whitespace=True)

    frame_index: int = Field(
        description="Zero-based index of the frame in the timeline_frames array",
        ge=0
    )
    timestamp_seconds: float = Field(
        description="Timestamp of this frame in seconds",
        ge=0
    )
    motion_level: Literal["low", "medium", "high"] = Field(
        description="Motion level at this frame: low, medium, or high"
    )
    relevance: Literal["key_frame", "transition_frame", "supporting"] = Field(
        description="How relevant this frame is: key_frame, transition_frame, or supporting"
    )


class ShotBoundary(BaseModel):
    """Information about how a shot boundary was determined."""
    model_config = ConfigDict(str_strip_whitespace=True)

    detected_by: Literal["motion_change", "scene_cut", "audio_cue", "manual"] = Field(
        description="How the boundary was detected"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level: high, medium, or low"
    )
    correlated_frames: List[int] = Field(
        description="Frame indices at the boundary",
        default_factory=list
    )


class ChronologicalShot(BaseModel):
    """A distinct shot or scene change in chronological order."""
    model_config = ConfigDict(str_strip_whitespace=True)

    shot_index: int = Field(
        description="Zero-based sequential index",
        ge=0
    )
    start_time_seconds: float = Field(
        description="When this shot begins in the video (seconds)",
        ge=0
    )
    end_time_seconds: float = Field(
        description="When this shot ends in the video (seconds)",
        ge=0
    )
    duration_seconds: float = Field(
        description="Approximate duration of this shot in seconds",
        gt=0
    )
    camera_direction: Optional[str] = Field(
        description="Camera movement and lens behavior (e.g., static tripod, slow push-in, handheld shake, smooth gimbal pan, drone orbit, zoom rack focus, whip pan, tilt down)",
        default=None
    )
    framing_type: Optional[str] = Field(
        description="Shot framing (e.g., extreme wide establishing, wide, medium wide, medium, medium close-up, close-up, extreme close-up, over-the-shoulder, point-of-view, top-down bird's-eye, low-angle hero, dutch angle)",
        default=None
    )
    action_and_motion: Optional[str] = Field(
        description="What happens in this shot — subject actions, object movements, physics, interactions, emotional expressions, text animations, UI interactions. Be specific and detailed enough to recreate the exact visual.",
        default=None
    )
    environment_context: Optional[str] = Field(
        description="The setting, background, and spatial context. Include surfaces, architecture, weather, time of day, crowd density, interior vs exterior, and any visible text or branding.",
        default=None
    )
    negative_elements: List[str] = Field(
        description="Visual elements that should NOT appear or that are absent in this shot (e.g., no people in background, no text overlays, no watermarks, no lens flare, no motion blur)",
        default_factory=list
    )
    frame_references: List[FrameReference] = Field(
        description="Which extracted frames informed this shot analysis. Correlate with ffmpeg timeline frames.",
        default_factory=list
    )
    shot_boundaries: Optional[ShotBoundary] = Field(
        description="Information about how this shot boundary was determined",
        default=None
    )

    @model_validator(mode='after')
    def _validate_time_range(self) -> 'ChronologicalShot':
        if self.start_time_seconds >= self.end_time_seconds:
            raise ValueError(
                f"start_time_seconds ({self.start_time_seconds}) must be less than "
                f"end_time_seconds ({self.end_time_seconds})"
            )
        return self


class GlobalAesthetic(BaseModel):
    """Overall visual style and technical characteristics of the video."""
    model_config = ConfigDict(str_strip_whitespace=True)

    art_style: str = Field(
        description="Overall visual style (e.g., photorealistic CGI, live-action documentary, 2D anime, stop-motion, screen recording, drone aerial, vlog handheld)"
    )
    color_grading: str = Field(
        description="Color palette and grading approach (e.g., warm golden hour, cool blue tones, high-contrast neon, natural daylight, desaturated moody)"
    )
    lighting_setup: str = Field(
        description="Lighting configuration (e.g., soft diffused studio lights, harsh direct sunlight, neon-lit night scene, natural window light, fluorescent office lighting)"
    )
    audio_mood: Optional[str] = Field(
        description="Audio mood classification (e.g., dynamic, contemplative, documentary, atmospheric)",
        default=None
    )


class UniversalBlueprint(BaseModel):
    """Complete production blueprint for recreating a video from scratch."""
    model_config = ConfigDict(str_strip_whitespace=True)

    global_aesthetic: GlobalAesthetic = Field(
        description="Overall visual style and technical characteristics"
    )
    chronological_shots: List[ChronologicalShot] = Field(
        description="Every distinct shot or scene change in the video, in chronological order. Include even brief cuts, transitions, and title cards.",
        min_length=1
    )

    def get_total_duration(self) -> float:
        """Calculate total video duration from shots."""
        if not self.chronological_shots:
            return 0.0
        return max(shot.end_time_seconds for shot in self.chronological_shots)

    def get_shot_count(self) -> int:
        """Get number of shots in the blueprint."""
        return len(self.chronological_shots)