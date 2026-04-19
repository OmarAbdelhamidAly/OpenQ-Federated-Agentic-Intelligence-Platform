"""Transcription Agent — Node 3.

Uses gemini-2.5-flash-preview via OpenRouter with native Audio Input.
Sends the full audio as Base64 and requests:
  - Full verbatim transcript
  - Speaker labels (SPEAKER_01, SPEAKER_02, ...)
  - Language detection

Cost: ~$0.30/1M audio tokens (cheapest OpenRouter audio model as of 2025)
Fallback: gemini-2.0-flash-001
"""
from __future__ import annotations
import json
import structlog
from typing import Any, Dict
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from app.domain.analysis.entities import AudioAnalysisState
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

TRANSCRIPTION_PROMPT = """You are an expert audio transcription and speaker diarization system.

Analyze the provided audio file and return a JSON response with the following structure:
{{
    "language": "detected language code (e.g., 'ar', 'en', 'fr')",
    "transcript": "Full verbatim transcript of the audio",
    "speaker_turns": [
        {{
            "speaker_id": "SPEAKER_01",
            "text": "what this speaker said",
            "start_time": 0.0,
            "end_time": 12.5
        }},
        ...
    ],
    "speakers_count": 2
}}

Rules:
- Use SPEAKER_01, SPEAKER_02, etc. for speaker labels
- Include ALL speech, even short utterances
- Timestamps are approximate seconds from the start of audio
- If only one speaker is present, use SPEAKER_01 for all turns
- Do NOT invent content — transcribe EXACTLY what is said
- Include filler words and natural speech patterns

Return ONLY valid JSON, no markdown, no explanation."""


def _get_transcription_llm(model: str):
    """Build OpenRouter LLM client for audio transcription."""
    return ChatOpenAI(
        model=model,
        temperature=0,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://openq.ai",
            "X-Title": "OpenQ Audio Intelligence",
        },
    )


async def transcription_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Transcribe audio and produce speaker-labeled turns via OpenRouter."""
    if state.get("error"):
        return {}

    audio_b64 = state.get("audio_b64", "")
    audio_format = state.get("audio_format", "wav")
    duration = state.get("audio_duration_seconds", 0)

    if not audio_b64:
        return {"error": "No audio data available for transcription"}

    # Normalize format for API (only wav and mp3 supported)
    api_format = "wav" if audio_format not in ("wav", "mp3") else audio_format

    logger.info(
        "transcription_started",
        model=settings.LLM_MODEL_AUDIO_TRANSCRIBE,
        duration_min=round(duration / 60, 1),
        format=api_format,
    )

    # Build the multimodal message with audio
    message = HumanMessage(content=[
        {"type": "text", "text": TRANSCRIPTION_PROMPT},
        {
            "type": "input_audio",
            "input_audio": {
                "data": audio_b64,
                "format": api_format,
            }
        }
    ])

    # Try primary model, then fallback
    for model_name in [
        settings.LLM_MODEL_AUDIO_TRANSCRIBE,
        settings.LLM_MODEL_AUDIO_TRANSCRIBE_FALLBACK,
    ]:
        try:
            llm = _get_transcription_llm(model_name)
            res = await llm.ainvoke([message])
            raw = res.content.strip()

            # Strip markdown code fences if present
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]

            data = json.loads(raw.strip())

            raw_transcript = data.get("transcript", "")
            speaker_turns = data.get("speaker_turns", [])
            language = data.get("language", "unknown")
            speakers_count = data.get("speakers_count", len(
                {t.get("speaker_id") for t in speaker_turns}
            ))

            logger.info(
                "transcription_complete",
                model=model_name,
                language=language,
                turns=len(speaker_turns),
                speakers=speakers_count,
                transcript_words=len(raw_transcript.split()),
            )

            return {
                "raw_transcript": raw_transcript,
                "speaker_turns": speaker_turns,
                "transcript_language": language,
                "speakers_count": speakers_count,
            }

        except json.JSONDecodeError as e:
            logger.warning("transcription_json_parse_failed", model=model_name, error=str(e))
            # Return raw text even if JSON parsing fails
            if 'raw' in locals() and raw:
                return {
                    "raw_transcript": raw,
                    "speaker_turns": [],
                    "transcript_language": "unknown",
                    "speakers_count": 1,
                }
        except Exception as e:
            logger.warning("transcription_model_failed", model=model_name, error=str(e))
            continue

    return {"error": "Transcription failed on all available models"}
