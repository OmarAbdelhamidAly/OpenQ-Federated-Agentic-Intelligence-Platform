"""Audio Profiler Agent — Node 1.

Inspects the uploaded audio file and extracts metadata:
  - duration, sample rate, channels, file size
  - rough speaker count estimate
  - validates audio format and size limits
"""
from __future__ import annotations
import os
import structlog
from typing import Any, Dict
from app.domain.analysis.entities import AudioAnalysisState
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

SUPPORTED_FORMATS = {"wav", "mp3", "m4a", "ogg", "flac", "webm"}
MAX_DURATION = settings.MAX_AUDIO_DURATION_SECONDS


async def audio_profiler_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Profile the audio file and extract metadata."""
    file_path = state.get("file_path", "")

    if not file_path or not os.path.exists(file_path):
        return {"error": f"Audio file not found: {file_path}"}

    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    if ext not in SUPPORTED_FORMATS:
        return {"error": f"Unsupported audio format: .{ext}. Supported: {SUPPORTED_FORMATS}"}

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > settings.MAX_AUDIO_SIZE_MB:
        return {"error": f"File too large: {file_size_mb:.1f}MB. Max: {settings.MAX_AUDIO_SIZE_MB}MB"}

    try:
        import librosa
        # Load only metadata — do NOT load audio into RAM yet
        duration = librosa.get_duration(path=file_path)
        # Get sample rate via soundfile (fast, no full decode)
        import soundfile as sf
        info = sf.info(file_path)
        sample_rate = info.samplerate
        channels = info.channels

    except Exception as e:
        # Fallback: use pydub for metadata (handles more formats)
        try:
            from pydub.utils import mediainfo
            info = mediainfo(file_path)
            duration = float(info.get("duration", 0))
            sample_rate = int(info.get("sample_rate", 16000))
            channels = int(info.get("channels", 1))
        except Exception as e2:
            logger.warning("audio_profiler_fallback_failed", error=str(e2))
            # Use safe defaults
            duration = 0.0
            sample_rate = 16000
            channels = 1

    if duration > MAX_DURATION:
        return {"error": f"Audio too long: {duration/3600:.1f}h. Max: {MAX_DURATION/3600:.1f}h"}

    # Rough speaker count estimate (purely heuristic — diarization will refine this)
    estimated_speakers = 2 if duration > 60 else 1

    logger.info(
        "audio_profiled",
        duration_min=round(duration / 60, 1),
        sample_rate=sample_rate,
        channels=channels,
        size_mb=round(file_size_mb, 2),
        format=ext,
    )

    return {
        "audio_format": ext,
        "audio_duration_seconds": round(duration, 2),
        "sample_rate": sample_rate,
        "channels": channels,
        "file_size_mb": round(file_size_mb, 2),
        "estimated_speakers": estimated_speakers,
        "error": None,
    }
