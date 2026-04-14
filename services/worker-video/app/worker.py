"""Video Worker — Multimodal Strategic Intelligence via OpenRouter.

Strategy:
  OpenRouter (OpenAI-compatible) does not support raw video byte streams.
  We use keyframe sampling to extract representative frames from the video,
  then send them as a sequence of base64 images to Gemini 1.5 Flash for
  temporal event analysis and entity extraction.
  
  Pipeline:
    1. Optionally compress video to 720p (saves tokens & processing time).
    2. Extract keyframes at a configurable interval (default: 1 frame / 5 seconds).
    3. Send frames as base64 images + prompt to OpenRouter.
    4. Parse structured JSON response for events, entities, and summary.
    5. Sync to Neo4j & persist to PostgreSQL.
"""

from __future__ import annotations
import asyncio
import uuid
import os
import base64
import json
import structlog
from typing import List
from openai import OpenAI
from celery import Celery
from app.infrastructure.config import settings
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
FRAME_INTERVAL_SECONDS = 5   # Extract 1 frame every N seconds
MAX_FRAMES = 12              # Maximum frames to send (controls token cost)

# ── Celery App ────────────────────────────────────────────────────────────────
app = Celery(
    "video_worker",
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


def _compress_to_720p(input_path: str) -> str:
    """Compress video to 720p if taller. Returns output path."""
    try:
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(input_path)
        if clip.h > 720:
            logger.info("compressing_video_to_720p", original_height=clip.h, path=input_path)
            base = os.path.splitext(input_path)[0]
            out_path = f"{base}_720p.mp4"
            clip.resize(height=720).write_videofile(out_path, codec="libx264", audio_codec="aac", logger=None)
            clip.close()
            return out_path
        clip.close()
        return input_path
    except Exception as e:
        logger.warning("video_compression_failed", error=str(e))
        return input_path


def _extract_keyframes(video_path: str) -> List[dict]:
    """Extract keyframes at FRAME_INTERVAL_SECONDS and return list of {timestamp, b64}."""
    frames = []
    try:
        from moviepy.editor import VideoFileClip
        from PIL import Image
        import io

        clip = VideoFileClip(video_path)
        duration = clip.duration
        times = []
        t = 0.0
        while t < duration and len(times) < MAX_FRAMES:
            times.append(t)
            t += FRAME_INTERVAL_SECONDS

        for ts in times:
            try:
                frame_array = clip.get_frame(ts)
                img = Image.fromarray(frame_array)
                # Resize frame to reduce payload size
                img.thumbnail((640, 360))
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=75)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                frames.append({"timestamp": round(ts, 1), "b64": b64})
            except Exception:
                continue

        clip.close()
        logger.info("keyframes_extracted", count=len(frames), duration=duration)
    except Exception as e:
        logger.error("keyframe_extraction_failed", error=str(e))
    return frames


# ── Celery Task ───────────────────────────────────────────────────────────────
@app.task(name="process_source_discovery")
def process_source_discovery(source_id: str, user_id: str):
    """Profiles a Video data source using OpenRouter (Gemini 1.5 Flash)."""
    return asyncio.run(_execute_video_discovery(source_id, user_id))


async def _execute_video_discovery(source_id: str, user_id: str):
    from sqlalchemy import select
    from app.infrastructure.database.postgres import async_session_factory
    from app.models.data_source import DataSource

    async with async_session_factory() as db:
        res = await db.execute(select(DataSource).where(DataSource.id == uuid.UUID(source_id)))
        source = res.scalar_one_or_none()
        if not source:
            logger.error("video_discovery_source_not_found", source_id=source_id)
            return

        if not source.file_path or not os.path.exists(source.file_path):
            logger.error("video_file_not_found", path=source.file_path)
            source.indexing_status = "failed"
            source.last_error = "File not found on disk"
            await db.commit()
            return

        logger.info("video_discovery_started", source_id=source_id, path=source.file_path)

        try:
            # 1. Compress to 720p
            processed_path = _compress_to_720p(source.file_path)
            was_compressed = processed_path != source.file_path

            # 2. Extract keyframes
            frames = _extract_keyframes(processed_path)
            if not frames:
                raise ValueError("No keyframes could be extracted from the video.")

            # 3. Build message with keyframes
            # First message: instruction text with frame timestamps
            timestamps_str = ", ".join([f"{f['timestamp']}s" for f in frames])
            text_block = {
                "type": "text",
                "text": (
                    f"You are an AI strategic analyst. I am providing {len(frames)} keyframes "
                    f"extracted every {FRAME_INTERVAL_SECONDS} seconds from a video file: "
                    f"'{os.path.basename(source.file_path)}'.\n"
                    f"Frame timestamps: [{timestamps_str}]\n\n"
                    "Analyze these frames in sequence to understand the video content. "
                    "Return ONLY a valid JSON object:\n"
                    "{\n"
                    '  "summary": "Overall narrative or content of the video",\n'
                    '  "events": [\n'
                    '    {"time": "0s-5s", "event": "Description of what happens in this segment"}\n'
                    '  ],\n'
                    '  "entities": [\n'
                    '    {"name": "...", "type": "person|location|object|text", "summary": "..."}\n'
                    '  ],\n'
                    '  "scene_count": 3,\n'
                    '  "dominant_colors": ["blue", "white"],\n'
                    '  "tags": ["keyword1", "keyword2"]\n'
                    "}\n\nRespond ONLY with JSON, no markdown."
                ),
            }

            messages_content = [text_block]
            for frame in frames:
                messages_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{frame['b64']}"
                    },
                })

            # 4. Call OpenRouter
            client = get_openrouter_client()
            response = client.chat.completions.create(
                model=settings.LLM_MODEL_VISION,
                messages=[{"role": "user", "content": messages_content}],
                extra_headers={
                    "HTTP-Referer": "https://insightify.ai",
                    "X-Title": "Insightify Video Intelligence",
                },
            )

            raw = response.choices[0].message.content
            text_response = raw.replace("```json", "").replace("```", "").strip()
            analysis_data = json.loads(text_response)

            # 5. Sync entities to Neo4j Knowledge Graph
            try:
                neo4j = Neo4jAdapter()
                neo4j.batch_upsert_multimodal_entities(
                    source_id=source_id,
                    media_id=source_id,
                    media_type="video",
                    entities=analysis_data.get("entities", []),
                )
            except Exception as neo4j_err:
                logger.warning("neo4j_sync_failed", error=str(neo4j_err))

            # 6. Persist results
            events = analysis_data.get("events", [])
            source.schema_json = {
                "source_type": "video",
                "summary": analysis_data.get("summary"),
                "event_count": len(events),
                "events_preview": events[:8],   # First 8 events for DataProfiler UI
                "entities": analysis_data.get("entities", []),
                "tags": analysis_data.get("tags", []),
                "scene_count": analysis_data.get("scene_count", 0),
                "dominant_colors": analysis_data.get("dominant_colors", []),
                "frames_analyzed": len(frames),
                "processed_at_720p": was_compressed,
                "format": os.path.splitext(source.file_path)[1].lstrip(".").upper(),
            }
            source.indexing_status = "done"
            await db.commit()
            logger.info("video_discovery_complete", source_id=source_id, events=len(events))

        except Exception as e:
            logger.error("video_discovery_failed", source_id=source_id, error=str(e))
            source.indexing_status = "failed"
            source.last_error = str(e)
            await db.commit()
