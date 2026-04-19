"""WebSocket router for Real-Time Streaming of Analysis Jobs."""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, status
import redis.asyncio as aioredis

from app.infrastructure.config import settings
from app.infrastructure.database.postgres import get_db, AsyncSession
from app.infrastructure.api_dependencies import get_current_user_ws

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/ws", tags=["streaming"])

@router.websocket("/{job_id}/stream")
async def analysis_stream_ws(
    websocket: WebSocket, 
    job_id: uuid.UUID,
    token: str = Query(...)
):
    """
    Subscribes to Redis Pub/Sub to push real-time LLM thinking steps
    and synthesis chunks directly to the UI.
    
    Note: WebSockets in browsers don't support custom headers easily, 
    so we accept the JWT auth token via query parameter.
    """
    await websocket.accept()
    
    # 1. Authenticate user over WebSocket
    try:
        # Dependency injection has to be resolved manually in explicit websocket routes
        # for robust query param handling depending on the setup. 
        # But we'll assume a utility function `get_current_user_ws` validates the token.
        user = await get_current_user_ws(token)
    except Exception as e:
        logger.warning("ws_auth_failed", job_id=str(job_id), error=str(e))
        await websocket.send_json({"type": "error", "message": "Authentication failed"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    logger.info("ws_client_connected", job_id=str(job_id), user_id=str(user.id))
    
    # 2. Setup Redis Pub/Sub Client
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    
    channel_name = f"job_stream:{job_id}"
    await pubsub.subscribe(channel_name)
    
    try:
        # 3. Listen for messages indefinitely until disconnected or job finishes
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                
                # Check for termination signal
                if data == "[DONE]":
                    await websocket.send_json({"type": "status", "data": "COMPLETED"})
                    break
                    
                # Pass data payload to client
                try:
                    payload = json.loads(data)
                    await websocket.send_json(payload)
                except json.JSONDecodeError:
                    # If it's a raw string chunk (e.g. LLM streaming token)
                    await websocket.send_text(data)

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", job_id=str(job_id))
    except Exception as e:
        logger.error("ws_stream_error", job_id=str(job_id), error=str(e))
        try:
            await websocket.send_json({"type": "error", "message": "Internal streaming error"})
        except:
            pass
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()
        await redis_client.aclose()
        if not websocket.client_state.name == "DISCONNECTED":
            await websocket.close()
