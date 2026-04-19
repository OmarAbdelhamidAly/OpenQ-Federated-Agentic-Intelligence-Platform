"""AudioAnalysisState — LangGraph state for the audio intelligence pipeline."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class SpeakerTurn(TypedDict, total=False):
    """A single speaker turn with timing and content."""
    speaker_id: str          # e.g., "SPEAKER_01"
    speaker_name: str        # Resolved name if identified (e.g., "Ahmed")
    text: str                # Transcribed text for this turn
    start_time: float        # Seconds from audio start
    end_time: float          # Seconds from audio end
    topics: List[str]        # Topics detected in this turn


class AudioSegment(TypedDict, total=False):
    """A raw audio segment produced by VAD / silence detection."""
    segment_index: int
    start_ms: int            # Start millisecond
    end_ms: int              # End millisecond
    duration_ms: int


class AudioAnalysisState(TypedDict, total=False):
    """
    Full LangGraph state for the audio intelligence pipeline.

    Flows through 9 nodes:
      audio_profiler → preprocessor → transcription → diarization →
      entity_extractor → summarizer → evaluator → memory_manager →
      output_assembler
    """

    # ── Input (from Celery task) ───────────────────────────────────────────────
    tenant_id: str
    user_id: str
    job_id: str
    source_id: str
    question: str            # The user's analysis question
    file_path: str           # Absolute path to uploaded audio file
    audio_format: str        # "wav" | "mp3" | "m4a" | "ogg" | "flac"
    participant_names: List[str]   # Optional: user-provided names for speakers

    # ── Node 1: Audio Profiler ─────────────────────────────────────────────────
    audio_duration_seconds: float
    sample_rate: int
    channels: int            # 1 = mono, 2 = stereo
    file_size_mb: float
    estimated_speakers: int  # Rough estimate from profiling

    # ── Node 2: Preprocessor (pydub normalization + silence segmentation) ─────
    cleaned_file_path: str   # Path to normalized audio file
    segments: List[AudioSegment]   # Silence-segmented chunks
    audio_b64: str           # Base64-encoded cleaned audio (for API)

    # ── Node 3: Transcription (gemini-2.5-flash-preview via OpenRouter) ────────
    raw_transcript: str      # Full verbatim transcript
    transcript_language: str # Detected language (e.g., "ar", "en")

    # ── Node 4: Diarization ────────────────────────────────────────────────────
    speaker_turns: List[SpeakerTurn]   # Structured speaker-labeled transcript
    speakers_count: int
    speakers_map: Dict[str, str]   # {"SPEAKER_01": "Ahmed", "SPEAKER_02": "Sara"}

    # ── Node 5: Entity Extraction (llama-3.1-8b) ──────────────────────────────
    entities: List[Dict[str, Any]]   # [{type, name, speaker, timestamp}]
    action_items: List[str]          # Commitments / tasks identified
    topics: List[str]                # Main discussion topics
    key_quotes: List[Dict[str, str]] # [{speaker, text, timestamp}]

    # ── Node 6: Summarizer (gemini-2.0-flash-lite) ────────────────────────────
    insight_report: str      # Full detailed analysis
    executive_summary: str   # 3-sentence executive summary

    # ── Node 7: RAG Evaluator (local SLMs — zero cost) ────────────────────────
    evaluation_metrics: Optional[Dict[str, Any]]   # Relevance / Attribution / Utilization

    # ── Node 8: Memory Manager (Qdrant + Neo4j) ───────────────────────────────
    qdrant_collection: str
    chunks_indexed: int

    # ── Error Handling ────────────────────────────────────────────────────────
    error: Optional[str]
    retry_count: int
