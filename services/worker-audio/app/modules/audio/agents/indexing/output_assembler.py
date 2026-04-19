"""Output Assembler Agent — Node 9.

Packages the final state into the clean output dict
that the Celery worker will persist to PostgreSQL.
"""
from __future__ import annotations
from typing import Any, Dict
from app.domain.analysis.entities import AudioAnalysisState


async def output_assembler(state: AudioAnalysisState) -> Dict[str, Any]:
    """Assemble the final output for database persistence."""
    speaker_turns = state.get("speaker_turns", [])
    speakers_map = state.get("speakers_map", {})

    return {
        "final_output": {
            # Core Results
            "insight_report": state.get("insight_report", ""),
            "executive_summary": state.get("executive_summary", ""),

            # Audio-specific intelligence
            "raw_transcript": state.get("raw_transcript", ""),
            "speaker_turns": speaker_turns,
            "speakers_map": speakers_map,
            "speakers_count": state.get("speakers_count", 1),
            "transcript_language": state.get("transcript_language", "unknown"),

            # Extracted intelligence
            "entities": state.get("entities", []),
            "action_items": state.get("action_items", []),
            "topics": state.get("topics", []),
            "key_quotes": state.get("key_quotes", []),

            # Audio metadata
            "audio_duration_seconds": state.get("audio_duration_seconds", 0),
            "audio_format": state.get("audio_format", ""),
            "chunks_indexed": state.get("chunks_indexed", 0),
            "qdrant_collection": state.get("qdrant_collection", ""),

            # RAG Quality
            "evaluation_metrics": state.get("evaluation_metrics"),

            # Error info
            "error": state.get("error"),
        }
    }
