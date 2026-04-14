"""Image Worker — Multimodal Strategic Intelligence via OpenRouter."""

from __future__ import annotations
import asyncio
import uuid
import os
import base64
import json
import structlog
from openai import OpenAI
from PIL import Image
from celery import Celery
from app.infrastructure.config import settings
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)

# ── Celery App ────────────────────────────────────────────────────────────────
app = Celery(
    "image_worker",
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

def _encode_image_b64(file_path: str) -> tuple[str, str]:
    """Return (base64_str, mime_type) for an image file."""
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/jpeg")
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), mime_type


# ── Celery Task ───────────────────────────────────────────────────────────────
@app.task(name="process_source_discovery")
def process_source_discovery(source_id: str, user_id: str):
    """Profiles an Image data source using OpenRouter (Gemini 1.5 Flash)."""
    return asyncio.run(_execute_image_discovery(source_id, user_id))


async def _execute_image_discovery(source_id: str, user_id: str):
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.data_source import DataSource

    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source:
            logger.error("image_discovery_source_not_found", source_id=source_id)
            return

        if not source.file_path or not os.path.exists(source.file_path):
            logger.error("image_file_not_found", path=source.file_path)
            source.indexing_status = "failed"
            source.last_error = "File not found on disk"
            await db.commit()
            return

        logger.info("image_discovery_started", source_id=source_id, path=source.file_path)

        try:
            # 1. Load image metadata
            with Image.open(source.file_path) as img:
                width, height = img.size
                fmt = img.format or "UNKNOWN"

            # 2. Encode image to base64 for OpenRouter
            b64_image, mime_type = _encode_image_b64(source.file_path)
            image_url = f"data:{mime_type};base64,{b64_image}"

            # 3. Call OpenRouter (Gemini 1.5 Flash — best for multimodal)
            client = get_openrouter_client()
            response = client.chat.completions.create(
                model=settings.LLM_MODEL_VISION,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Analyze this image for strategic intelligence. "
                                    "Return ONLY a valid JSON object with these fields:\n"
                                    "- description: A detailed summary of the scene.\n"
                                    "- entities: A list like [{\"name\": \"...\", \"type\": \"object|person|text\", \"summary\": \"...\"}]\n"
                                    "- tags: A list of relevant keywords.\n"
                                    "- detected_text: Any OCR text found in the image (empty string if none).\n"
                                    "Respond ONLY with the JSON, no markdown."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            },
                        ],
                    }
                ],
                extra_headers={
                    "HTTP-Referer": "https://insightify.ai",
                    "X-Title": "Insightify Image Intelligence",
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
                    media_type="image",
                    entities=analysis_data.get("entities", []),
                )
            except Exception as neo4j_err:
                logger.warning("neo4j_sync_failed", error=str(neo4j_err))

            # 5. Persist results
            source.schema_json = {
                "source_type": "image",
                "description": analysis_data.get("description"),
                "summary": analysis_data.get("description"),
                "tags": analysis_data.get("tags", []),
                "detected_text": analysis_data.get("detected_text", ""),
                "entities": analysis_data.get("entities", []),
                "dimensions": f"{width}x{height}",
                "format": fmt,
            }
            source.indexing_status = "done"
            await db.commit()
            logger.info("image_discovery_complete", source_id=source_id)

        except Exception as e:
            logger.error("image_discovery_failed", source_id=source_id, error=str(e))
            source.indexing_status = "failed"
            source.last_error = str(e)
            await db.commit()
