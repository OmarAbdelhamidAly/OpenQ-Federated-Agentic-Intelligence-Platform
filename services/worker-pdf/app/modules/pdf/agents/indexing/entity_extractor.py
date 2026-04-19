"""PDF Entity Extractor Agent.

Extracts structured metadata (Entities, Topics, Action Items) from PDF text content
to build the foundation of the Knowledge Graph.
"""
from __future__ import annotations
import json
import structlog
from typing import Any, Dict, List
from langchain_openai import ChatOpenAI
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

async def extract_pdf_entities(text_chunks: List[Any], question: str = "") -> Dict[str, Any]:
    """Analyze PDF text chunks and extract structured information."""
    if not text_chunks:
        return {"entities": [], "topics": []}

    # Samples text from across the document to build a global picture
    # PDF documents can be huge, so we sample first, middle and last chunks
    sample_size = min(len(text_chunks), 15)
    step = max(1, len(text_chunks) // sample_size)
    sampled_chunks = text_chunks[::step][:15]
    
    combined_text = "\n\n".join([c.text if hasattr(c, 'text') else str(c.get('text', '')) for c in sampled_chunks])
    context_text = combined_text[:8000] # Cap for context window

    prompt = f"""You are an elite Document Intelligence AI. 
Analyze the following excerpts from a PDF document and extract strategic metadata.

Document Excerpts:
{context_text}

Return ONLY valid JSON with this exact structure:
{{
    "entities": [
        {{"type": "Person|Organization|Location|Date|Technology|Concept", "name": "...", "context": "brief significance"}}
    ],
    "topics": [
        "Major Topic 1", "Major Topic 2"
    ],
    "document_summary": "One sentence high-level summary of the whole file."
}}

Extract maximum 15 critical entities and 8 main topics."""

    try:
        llm = ChatOpenAI(
            # Using the fast/cheap model for indexing
            model="meta-llama/llama-3.1-8b-instruct",
            temperature=0,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://openq.ai",
                "X-Title": "OpenQ PDF Intelligence",
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
        logger.info("pdf_entity_extraction_complete", 
                    entities=len(data.get("entities", [])), 
                    topics=len(data.get("topics", [])))
        return data

    except Exception as e:
        logger.error("pdf_entity_extraction_failed", error=str(e))
        return {"entities": [], "topics": [], "document_summary": "N/A"}
