"""Preprocessor Agent — Node 2.

Responsibilities:
  1. Normalize audio volume (pydub AudioNormalize)
  2. Convert to mono WAV at 16kHz (Gemini's preferred format)
  3. Encode to Base64 for OpenRouter API
  4. Detect silence segments for rough speaker-turn estimation
"""
from __future__ import annotations
import os
import base64
import uuid
import structlog
from typing import Any, Dict, List
from app.domain.analysis.entities import AudioAnalysisState, AudioSegment

logger = structlog.get_logger(__name__)

# Silence detection thresholds
SILENCE_THRESH_DB = -40    # dBFS — quieter than this = silence
MIN_SILENCE_MS = 700       # Minimum silence duration to split on
KEEP_SILENCE_MS = 200      # Keep this much silence at boundaries


async def preprocessor_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Normalize, convert, and segment the audio file."""
    file_path = state.get("file_path", "")
    if state.get("error"):
        return {}  # Pass through errors from profiler

    try:
        from pydub import AudioSegment as PydubSegment
        from pydub import silence as pydub_silence

        logger.info("audio_preprocessing_started", file=os.path.basename(file_path))

        # ── 1. Load Audio ──────────────────────────────────────────────────────
        audio = PydubSegment.from_file(file_path)

        # ── 2. Normalize: Convert to Mono, 16kHz (optimal for ASR) ────────────
        audio = audio.set_channels(1)           # Force mono
        audio = audio.set_frame_rate(16000)     # 16kHz sample rate

        # Normalize volume to -14 dBFS (industry standard for speech)
        from pydub.effects import normalize
        audio = normalize(audio)

        # ── 3. Export cleaned WAV to temp file ───────────────────────────────
        cleaned_path = f"/tmp/tenants/audio_clean_{uuid.uuid4().hex}.wav"
        os.makedirs(os.path.dirname(cleaned_path), exist_ok=True)
        audio.export(cleaned_path, format="wav")

        # ── 4. Encode to Base64 for OpenRouter API ───────────────────────────
        with open(cleaned_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        # ── 5. Detect Silence Segments (for rough turn-taking hints) ─────────
        silence_ranges = pydub_silence.detect_silence(
            audio,
            min_silence_len=MIN_SILENCE_MS,
            silence_thresh=SILENCE_THRESH_DB,
        )

        # Build non-silence segments (speech segments)
        speech_segments: List[AudioSegment] = []
        prev_end = 0
        for idx, (silence_start, silence_end) in enumerate(silence_ranges):
            if silence_start > prev_end:
                speech_segments.append({
                    "segment_index": len(speech_segments),
                    "start_ms": prev_end,
                    "end_ms": silence_start,
                    "duration_ms": silence_start - prev_end,
                })
            prev_end = silence_end

        # Add final segment if audio continues after last silence
        if prev_end < len(audio):
            speech_segments.append({
                "segment_index": len(speech_segments),
                "start_ms": prev_end,
                "end_ms": len(audio),
                "duration_ms": len(audio) - prev_end,
            })

        logger.info(
            "audio_preprocessing_complete",
            speech_segments=len(speech_segments),
            cleaned_path=cleaned_path,
            b64_size_kb=round(len(audio_b64) / 1024, 1),
        )

        return {
            "cleaned_file_path": cleaned_path,
            "audio_b64": audio_b64,
            "segments": speech_segments,
        }

    except Exception as e:
        logger.error("audio_preprocessing_failed", error=str(e))
        # Non-fatal: try to encode raw file as fallback
        try:
            with open(file_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("utf-8")
            return {
                "cleaned_file_path": file_path,
                "audio_b64": audio_b64,
                "segments": [],
            }
        except Exception as e2:
            return {"error": f"Audio preprocessing failed: {str(e2)}"}
