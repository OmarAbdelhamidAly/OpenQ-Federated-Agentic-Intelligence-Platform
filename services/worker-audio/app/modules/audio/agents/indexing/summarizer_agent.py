"""Summarizer Agent — Node 6.

Uses gemini-2.0-flash-lite-001 (cheap text model) to generate:
  - Full insight report answering the user's question
  - 3-sentence executive summary
"""
from __future__ import annotations
import structlog
from typing import Any, Dict
from langchain_openai import ChatOpenAI
from app.domain.analysis.entities import AudioAnalysisState
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)


def _build_context(state: AudioAnalysisState) -> str:
    turns = state.get("speaker_turns", [])
    topics = state.get("topics", [])
    action_items = state.get("action_items", [])
    entities = state.get("entities", [])
    key_quotes = state.get("key_quotes", [])

    parts = []
    if topics:
        parts.append(f"Main Topics: {', '.join(topics)}")
    if action_items:
        parts.append("Action Items:\n" + "\n".join(f"  - {a}" for a in action_items))
    if key_quotes:
        parts.append("Key Quotes:\n" + "\n".join(
            f"  [{q.get('timestamp','')}] {q.get('speaker','')}: \"{q.get('text','')}\"" for q in key_quotes[:5]
        ))
    if entities:
        entity_summary = ", ".join(f"{e.get('name')} ({e.get('type')})" for e in entities[:8])
        parts.append(f"Key Entities: {entity_summary}")

    transcript_sample = "\n".join(
        f"{t.get('speaker_name', t.get('speaker_id','Speaker'))}: {t.get('text','')}"
        for t in turns[:20]
    )
    parts.append(f"Transcript Sample:\n{transcript_sample}")
    return "\n\n".join(parts)


async def summarizer_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Generate the insight report and executive summary."""
    if state.get("error"):
        return {}

    question = state.get("question", "Provide a comprehensive analysis of this audio recording.")
    duration = state.get("audio_duration_seconds", 0)
    speakers_count = state.get("speakers_count", 1)
    language = state.get("transcript_language", "unknown")
    context = _build_context(state)

    prompt = f"""You are an expert business intelligence analyst specializing in audio content analysis.

Audio Metadata:
- Duration: {duration/60:.1f} minutes
- Speakers: {speakers_count}
- Language: {language}

Extracted Intelligence:
{context}

User's Question: {question}

Generate a comprehensive analysis report. Structure your response as:

## Executive Summary
[3 sentences maximum — key outcome and most important insight]

## Detailed Analysis
[Answer the user's question directly with evidence from the transcript]

## Key Findings
[Bullet points of the most important discoveries]

## Speaker Contributions
[What each speaker contributed to the discussion]

## Recommendations
[3-5 actionable recommendations based on the discussion]

Be specific, cite speaker names and timestamps where relevant."""

    try:
        llm = ChatOpenAI(
            model=settings.LLM_MODEL_AUDIO_SUMMARY,
            temperature=0.3,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://openq.ai",
                "X-Title": "OpenQ Audio Intelligence",
            },
        )

        res = await llm.ainvoke(prompt)
        full_report = res.content.strip()

        # Extract executive summary (first section)
        exec_summary = ""
        if "## Executive Summary" in full_report:
            parts = full_report.split("## Executive Summary")
            if len(parts) > 1:
                summary_section = parts[1].split("##")[0].strip()
                exec_summary = summary_section

        logger.info(
            "summarizer_complete",
            model=settings.LLM_MODEL_AUDIO_SUMMARY,
            report_words=len(full_report.split()),
        )

        return {
            "insight_report": full_report,
            "executive_summary": exec_summary,
        }

    except Exception as e:
        logger.error("summarizer_failed", error=str(e))
        return {
            "insight_report": f"Summary generation failed: {str(e)}",
            "executive_summary": "Analysis unavailable.",
        }
