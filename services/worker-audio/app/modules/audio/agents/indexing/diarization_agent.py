"""Diarization Agent — Node 4.

Resolves and cleans speaker labels, maps participant names if provided,
and produces the final structured speaker_turns list ready for indexing.
"""
from __future__ import annotations
import json
import structlog
from typing import Any, Dict, List
from langchain_openai import ChatOpenAI
from app.domain.analysis.entities import AudioAnalysisState, SpeakerTurn
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)


async def diarization_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """
    Resolves speaker identities and enriches speaker turns.

    If participant_names are provided by the user (e.g., ["Ahmed", "Sara"]),
    we use the LLM to map SPEAKER_01 → Ahmed, SPEAKER_02 → Sara based on
    context clues in the transcript.

    Otherwise, we keep the SPEAKER_XX labels.
    """
    if state.get("error"):
        return {}

    speaker_turns: List[SpeakerTurn] = state.get("speaker_turns", [])
    participant_names: List[str] = state.get("participant_names", [])
    raw_transcript = state.get("raw_transcript", "")
    speakers_count = state.get("speakers_count", 1)

    if not speaker_turns:
        logger.warning("diarization_no_turns", reason="transcription produced no speaker turns")
        # Create a single-speaker fallback from raw transcript
        fallback_turns = [{
            "speaker_id": "SPEAKER_01",
            "speaker_name": participant_names[0] if participant_names else "SPEAKER_01",
            "text": raw_transcript,
            "start_time": 0.0,
            "end_time": state.get("audio_duration_seconds", 0.0),
            "topics": [],
        }]
        return {
            "speaker_turns": fallback_turns,
            "speakers_map": {"SPEAKER_01": participant_names[0] if participant_names else "SPEAKER_01"},
            "speakers_count": 1,
        }

    # ── Build default speakers_map ──────────────────────────────────────────
    unique_speakers = sorted({t.get("speaker_id", "SPEAKER_01") for t in speaker_turns})
    speakers_map: Dict[str, str] = {}

    if participant_names and len(participant_names) >= len(unique_speakers):
        # Direct mapping: SPEAKER_01 → Ahmed, SPEAKER_02 → Sara
        for i, speaker_id in enumerate(unique_speakers):
            speakers_map[speaker_id] = participant_names[i]
    elif participant_names and len(participant_names) < len(unique_speakers):
        # Partial mapping — use LLM to figure out who is who
        speakers_map = await _llm_resolve_speakers(
            speaker_turns=speaker_turns,
            participant_names=participant_names,
            raw_transcript=raw_transcript,
        )
    else:
        # No names provided — keep SPEAKER_XX labels
        for speaker_id in unique_speakers:
            speakers_map[speaker_id] = speaker_id

    # ── Enrich speaker_turns with resolved names ────────────────────────────
    enriched_turns: List[SpeakerTurn] = []
    for turn in speaker_turns:
        speaker_id = turn.get("speaker_id", "SPEAKER_01")
        enriched_turns.append({
            **turn,
            "speaker_name": speakers_map.get(speaker_id, speaker_id),
            "topics": turn.get("topics", []),
        })

    logger.info(
        "diarization_complete",
        speakers=len(unique_speakers),
        turns=len(enriched_turns),
        map=speakers_map,
    )

    return {
        "speaker_turns": enriched_turns,
        "speakers_map": speakers_map,
        "speakers_count": len(unique_speakers),
    }


async def _llm_resolve_speakers(
    speaker_turns: List[SpeakerTurn],
    participant_names: List[str],
    raw_transcript: str,
) -> Dict[str, str]:
    """Use Gemini Flash Lite to infer who is who from context."""
    try:
        llm = ChatOpenAI(
            model=settings.LLM_MODEL_AUDIO_SUMMARY,  # Cheap text model
            temperature=0,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "https://openq.ai", "X-Title": "OpenQ"},
        )

        # Sample turns distributed across the transcript for better speaker coverage
        # (speakers active only in the middle/end are missed by first-10 sampling)
        n = len(speaker_turns)
        if n <= 20:
            sample = speaker_turns
        else:
            # Take 7 from start, 7 from middle, 6 from end
            mid = n // 2
            sample = speaker_turns[:7] + speaker_turns[mid-3:mid+4] + speaker_turns[-6:]
        sample_text = "\n".join([
            f"{t.get('speaker_id')}: {t.get('text', '')[:100]}"
            for t in sample
        ])

        prompt = f"""The following is an excerpt from an audio transcript.
Known participants: {', '.join(participant_names)}
Speaker IDs in transcript: {list({t.get('speaker_id') for t in speaker_turns})}

Transcript excerpt:
{sample_text}

Based on context, map each speaker ID to a participant name.
Respond with ONLY valid JSON like: {{"SPEAKER_01": "Ahmed", "SPEAKER_02": "Sara"}}
If you cannot determine a mapping with confidence, use the speaker ID as the name."""

        res = await llm.ainvoke(prompt)
        raw = res.content.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("speaker_resolution_failed", error=str(e))
        # Fallback: assign names in order
        unique = sorted({t.get("speaker_id", "SPEAKER_01") for t in speaker_turns})
        return {
            spk: participant_names[i] if i < len(participant_names) else spk
            for i, spk in enumerate(unique)
        }
