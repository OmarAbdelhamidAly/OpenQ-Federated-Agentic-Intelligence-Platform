"""Voice router — Speech-to-Text (STT) and metadata for TTS."""
import os
import structlog
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from typing import Annotated
from groq import Groq
from app.infrastructure.config import settings
from app.infrastructure.api_dependencies import get_current_user
from app.models.user import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

@router.post("/stt")
async def speech_to_text(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    """Transcribe audio using Groq Whisper-large-v3."""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    client = Groq(api_key=settings.GROQ_API_KEY)
    
    try:
        # Read file into memory
        content = await file.read()
        filename = file.filename or "audio.webm"
        
        # Groq expects a file-like object with a name attribute
        from io import BytesIO
        audio_file = BytesIO(content)
        audio_file.name = filename

        transcription = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3",
            response_format="json",
            language="en", # Can be auto-detected if removed
            temperature=0.0,
        )
        
        logger.info("stt_success", user_id=str(current_user.id), length=len(content))
        return {"text": transcription.text}

    except Exception as e:
        logger.error("stt_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
