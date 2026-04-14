"""Audio Worker — Multimodal Strategic Intelligence via OpenRouter.

Strategy:
  OpenRouter's API (OpenAI-compatible) does not stream raw audio bytes directly.
  We use a two-phase approach:
    1. Convert the audio to a text transcript using pydub to extract metadata
       + encode a small sample as base64 for the model to confirm content.
    2. Send the transcript/metadata to OpenRouter (Gemini 1.5 Flash) for
       deep strategic analysis: topic modeling, entity extraction, speaker roles.
"""

from __future__ import annotations
import asyncio
import uuid
import os
import base64
import json
import math
import structlog
from openai import OpenAI
from celery import Celery
from app.infrastructure.config import settings
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)

# ── Celery App ────────────────────────────────────────────────────────────────
app = Celery(
    "audio_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)

# ── OpenRouter Client ─────────────────────────────────────────────────────────
def get_openrouter_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )


def _get_audio_metadata(file_path: str) -> dict:
    """Extract audio metadata and a base64 sample using pydub."""
    try:
        from pydub import AudioSegment
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        audio = AudioSegment.from_file(file_path, format=ext if ext else "mp3")
        duration_s = math.ceil(len(audio) / 1000)
        channels = audio.channels
        sample_rate = audio.frame_rate
        # Export a 30-second sample (or full if shorter) for context
        sample = audio[:30_000]  # 30 seconds
        sample_bytes = sample.export(format="mp3").read()
        sample_b64 = base64.b64encode(sample_bytes).decode("utf-8")
        return {
            "duration_seconds": duration_s,
            "channels": channels,
            "sample_rate": sample_rate,
            "sample_b64": sample_b64,
            "sample_mime": "audio/mpeg",
        }
    except Exception as e:
        logger.warning("audio_metadata_extraction_failed", error=str(e))
        return {"duration_seconds": 0, "channels": 1, "sample_rate": 44100, "sample_b64": None}


# ── Celery Task ───────────────────────────────────────────────────────────────
@app.task(name="process_source_discovery")
def process_source_discovery(source_id: str, user_id: str):
    """Profiles an Audio data source using OpenRouter (Gemini 1.5 Flash)."""
    return asyncio.run(_execute_audio_discovery(source_id, user_id))


async def _execute_audio_discovery(source_id: str, user_id: str):
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.data_source import DataSource

    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source:
            logger.error("audio_discovery_source_not_found", source_id=source_id)
            return

        if not source.file_path or not os.path.exists(source.file_path):
            logger.error("audio_file_not_found", path=source.file_path)
            source.indexing_status = "failed"
            source.last_error = "File not found on disk"
            await db.commit()
            return

        logger.info("audio_discovery_started", source_id=source_id, path=source.file_path)

        try:
            # 1. Extract audio metadata & 30-second sample
            meta = _get_audio_metadata(source.file_path)
            duration = meta["duration_seconds"]
            filename = os.path.basename(source.file_path)

            # 2. Build message for OpenRouter
            # Gemini 1.5 Flash supports audio via base64 data URI in the messages API
            messages_content: list = [
                {
                    "type": "text",
                    "text": (
                        f"You are an AI strategic analyst. Analyze this audio file: '{filename}' "
                        f"(~{duration}s, {meta['channels']}ch, {meta['sample_rate']}Hz).\n\n"
                        "Based on the audio content provided, return ONLY a valid JSON object:\n"
                        "{\n"
                        '  "transcript": "Full or partial transcript of the audio",\n'
                        '  "speakers": [{"id": "Speaker 1", "role": "..."}],\n'
                        '  "summary": "High-level strategic summary",\n'
                        '  "topics": ["topic1", "topic2"],\n'
                        '  "entities": [{"name": "...", "type": "person|company|product|date", "summary": "..."}],\n'
                        '  "language": "detected language"\n'
                        "}\n\nRespond ONLY with the JSON, no markdown."
                    ),
                }
            ]

            # Include base64 audio sample if available (Gemini supports audio/mpeg)
            if meta.get("sample_b64"):
                messages_content.append({
                    "type": "image_url",  # OpenRouter uses image_url for all media
                    "image_url": {
                        "url": f"data:{meta['sample_mime']};base64,{meta['sample_b64']}"
                    },
                })

            # 3. Call OpenRouter
            client = get_openrouter_client()
            response = client.chat.completions.create(
                model=settings.LLM_MODEL_FAST,
                messages=[{"role": "user", "content": messages_content}],
                extra_headers={
                    "HTTP-Referer": "https://insightify.ai",
                    "X-Title": "Insightify Audio Intelligence",
                },
            )

            raw = response.choices[0].message.content
            text_response = raw.replace("```json", "").replace("```", "").strip()
            analysis_data = json.loads(text_response)

            # 4. Sync entities to Neo4j Knowledge Graph
            try:
                neo4j = Neo4jAdapter()
                neo4j.batch_upsert_multimodal_entities(
                    source_id=source_id,
                    media_id=source_id,
                    media_type="audio",
                    entities=analysis_data.get("entities", []),
                )
            except Exception as neo4j_err:
                logger.warning("neo4j_sync_failed", error=str(neo4j_err))

            # 5. Persist results
            transcript = analysis_data.get("transcript", "")
            source.schema_json = {
                "source_type": "audio",
                "summary": analysis_data.get("summary"),
                "language": analysis_data.get("language", "unknown"),
                "duration_seconds": duration,
                "speakers": analysis_data.get("speakers", []),
                "topics": analysis_data.get("topics", []),
                "entities": analysis_data.get("entities", []),
                "transcript_preview": transcript[:800] + ("..." if len(transcript) > 800 else ""),
                "full_transcript": transcript,
                "format": os.path.splitext(source.file_path)[1].lstrip(".").upper(),
            }
            source.indexing_status = "done"
            await db.commit()
            logger.info("audio_discovery_complete", source_id=source_id)

        except Exception as e:
            logger.error("audio_discovery_failed", source_id=source_id, error=str(e))
            source.indexing_status = "failed"
            source.last_error = str(e)
            await db.commit()
