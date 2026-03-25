"""RAG Retrieval Utilities — fetches context from Qdrant."""

import os
from typing import List, Optional
from qdrant_client import QdrantClient


async def get_kb_context(kb_id: Optional[str], query: str, limit: int = 3) -> str:
    """Search for relevant chunks in the specified knowledge base."""
    if not kb_id:
        return ""
    
    try:
        collection_name = f"kb_{str(kb_id).replace('-', '')}"
        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        client.set_model("BAAI/bge-small-en-v1.5")
        
        results = client.query(
            collection_name=collection_name,
            query_text=query,
            limit=limit
        )
        
        if not results:
            return ""
            
        context_parts = []
        for res in results:
            context_parts.append(f"--- Context (Source: {res.metadata.get('name', 'Unknown')}) ---\n{res.document}")
            
        return "\n\n".join(context_parts)
    except Exception as e:
        # Silently fail for now to avoid breaking the pipeline if Qdrant is down
        print(f"Retrieval error: {e}")
        return ""
