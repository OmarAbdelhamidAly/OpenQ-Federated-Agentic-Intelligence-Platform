"""Entity Extractor Agent — Node 5.

Uses meta-llama/llama-3.1-8b-instruct (cheapest OpenRouter text model) to:
  - Extract named entities (people, organizations, dates, amounts)
  - Identify action items and commitments
  - Detect main discussion topics
  - Pull key quotes per speaker
"""
from __future__ import annotations
import json
import structlog
from typing import Any, Dict
from langchain_openai import ChatOpenAI
from app.domain.analysis.entities import AudioAnalysisState
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)


def _format_transcript_for_entity(speaker_turns) -> str:
    """Format speaker turns into a readable transcript for entity extraction."""
    lines = []
    for turn in speaker_turns:
        name = turn.get("speaker_name") or turn.get("speaker_id", "Speaker")
        text = turn.get("text", "")
        ts = turn.get("start_time", 0)
        minutes = int(ts // 60)
        seconds = int(ts % 60)
        lines.append(f"[{minutes:02d}:{seconds:02d}] {name}: {text}")
    return "\n".join(lines)


async def entity_extractor_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Extract entities, topics, action items, and key quotes from the transcript."""
    if state.get("error"):
        return {}

    speaker_turns = state.get("speaker_turns", [])
    question = state.get("question", "")

    if not speaker_turns:
        return {
            "entities": [],
            "action_items": [],
            "topics": [],
            "key_quotes": [],
        }

    formatted_transcript = _format_transcript_for_entity(speaker_turns)
    # Limit to avoid token overflow
    transcript_sample = formatted_transcript[:6000]

    prompt = f"""You are an expert information extraction AI.

Analyze the following audio transcript and extract structured information.

User's Analysis Question: {question or 'General analysis'}

Transcript:
{transcript_sample}

Return ONLY valid JSON with this exact structure:
{{
    "entities": [
        {{"type": "Person|Organization|Location|Date|Amount|Product", "name": "...", "speaker": "who mentioned it", "context": "brief context"}}
    ],
    "action_items": [
        "Clear action item or commitment mentioned (who does what by when)"
    ],
    "topics": [
        "Main topic 1", "Main topic 2"
    ],
    "key_quotes": [
        {{"speaker": "name", "text": "exact quote", "timestamp": "MM:SS", "significance": "why important"}}
    ]
}}

Extract maximum 10 entities, 10 action items, 8 topics, 5 key quotes.
Focus on items most relevant to: {question or 'the overall discussion'}"""

    try:
        llm = ChatOpenAI(
            model=settings.LLM_MODEL_AUDIO_ENTITY,
            temperature=0,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://openq.ai",
                "X-Title": "OpenQ Audio Intelligence",
            },
        )

        res = await llm.ainvoke(prompt)
        raw = res.content.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]

        data = json.loads(raw.strip())

        entities = data.get("entities", [])
        action_items = data.get("action_items", [])
        topics = data.get("topics", [])
        key_quotes = data.get("key_quotes", [])

        logger.info(
            "entity_extraction_complete",
            model=settings.LLM_MODEL_AUDIO_ENTITY,
            entities=len(entities),
            action_items=len(action_items),
            topics=len(topics),
            key_quotes=len(key_quotes),
        )

        return {
            "entities": entities,
            "action_items": action_items,
            "topics": topics,
            "key_quotes": key_quotes,
        }

    except Exception as e:
        logger.error("entity_extraction_failed", error=str(e))
        return {
            "entities": [],
            "action_items": [],
            "topics": [],
            "key_quotes": [],
        }
