"""Fast PDF Retrieval — HNSW Dense Search + MMR + Cross-Encoder Reranking.

Query pipeline:
  1. FastEmbed the user query → dense vector
  2. Qdrant HNSW search → top 20 candidates
  3. MMR (Max Marginal Relevance) → diverse top 10
  4. Cross-Encoder reranking → sorted top 5
  5. Return formatted context string for LLM
"""
from __future__ import annotations

import os
from typing import List, Tuple, Any, Dict, Optional
import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# ── Lazy singletons ────────────────────────────────────────────────────────────
_embed_model = None
_reranker = None


def _get_embedding_model():
    global _embed_model
    if _embed_model is None:
        from fastembed import TextEmbeddingModel
        _embed_model = TextEmbeddingModel(model_name="BAAI/bge-small-en-v1.5")
    return _embed_model


def _get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
            logger.info("reranker_loaded")
        except Exception as e:
            logger.warning("reranker_unavailable", error=str(e))
            _reranker = None
    return _reranker


# ── MMR Implementation ─────────────────────────────────────────────────────────

def _mmr(
    query_vector: List[float],
    candidates: List[Tuple[str, List[float], float, Dict]],
    k: int = 10,
    lambda_param: float = 0.6,
) -> List[Tuple[str, float, Dict]]:
    """Max Marginal Relevance — balance relevance and diversity.
    
    lambda_param: 1.0 = pure relevance, 0.0 = pure diversity.
    Returns list of (text, score, payload) tuples.
    """
    if not candidates:
        return []

    q = np.array(query_vector, dtype=np.float32)
    q_norm = q / (np.linalg.norm(q) + 1e-10)

    vecs = np.array([c[1] for c in candidates], dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
    vecs_norm = vecs / norms

    rel_scores = vecs_norm @ q_norm  # cosine similarity to query

    selected_indices = []
    remaining = list(range(len(candidates)))

    for _ in range(min(k, len(candidates))):
        if not remaining:
            break

        if not selected_indices:
            # First: pick highest relevance
            best = max(remaining, key=lambda i: rel_scores[i])
        else:
            # MMR score = lambda * relevance - (1-lambda) * max_similarity_to_selected
            sel_vecs = vecs_norm[selected_indices]
            scores = []
            for i in remaining:
                sim_to_selected = np.max(vecs_norm[i] @ sel_vecs.T)
                mmr_score = lambda_param * rel_scores[i] - (1 - lambda_param) * sim_to_selected
                scores.append((i, mmr_score))
            best = max(scores, key=lambda x: x[1])[0]

        selected_indices.append(best)
        remaining.remove(best)

    return [
        (candidates[i][0], float(rel_scores[i]), candidates[i][3])
        for i in selected_indices
    ]


# ── Public API ─────────────────────────────────────────────────────────────────

async def fast_retrieve_context(
    source_id: str,
    query: str,
    top_k_final: int = 5,
    top_k_hnsw: int = 20,
    top_k_mmr: int = 10,
) -> str:
    """Full fast retrieval chain: HNSW → MMR → Reranking → context string.
    
    Returns a formatted string for the LLM context window.
    """
    from app.modules.pdf.utils.qdrant_hnsw import QdrantHNSWManager

    collection_name = f"fast_ds_{source_id.replace('-', '')}"
    qdrant = QdrantHNSWManager(collection_name=collection_name)

    # ── 1. Embed query ───────────────────────────────────────────────────────
    model = _get_embedding_model()
    query_vec = list(model.embed([query]))[0]
    query_vec = list(query_vec)

    # ── 2. HNSW Dense Search ─────────────────────────────────────────────────
    try:
        results = qdrant.search(
            query_vector=query_vec,
            limit=top_k_hnsw,
            filter_payload={"source_id": source_id},
        )
    except Exception as e:
        logger.error("hnsw_search_failed", source_id=source_id, error=str(e))
        return ""

    if not results:
        logger.warning("hnsw_no_results", source_id=source_id)
        return ""

    logger.info("hnsw_candidates", count=len(results))

    # ── 3. MMR Diversification ───────────────────────────────────────────────
    # Build candidates: (text, vector, score, payload)
    # We need to re-fetch vectors for MMR — for efficiency, use score as proxy
    # and skip re-fetching by using result scores
    candidates_for_mmr = [
        (
            r.payload.get("text", ""),
            query_vec,   # Use query_vec as placeholder since we sort by relevance
            r.score,
            r.payload,
        )
        for r in results
    ]

    # Better MMR: fetch the actual vectors
    try:
        point_ids = [r.id for r in results]
        fetched = qdrant.client.retrieve(
            collection_name=collection_name,
            ids=point_ids,
            with_vectors=True,
            with_payload=True,
        )
        candidates_for_mmr = [
            (
                f.payload.get("text", ""),
                list(f.vector),
                0.0,
                f.payload,
            )
            for f in fetched
            if f.vector
        ]
    except Exception as e:
        logger.warning("mmr_vector_fetch_skipped", error=str(e))

    mmr_results = _mmr(
        query_vector=query_vec,
        candidates=candidates_for_mmr,
        k=top_k_mmr,
        lambda_param=0.6,
    )
    logger.info("mmr_selected", count=len(mmr_results))

    # ── 4. Cross-Encoder Reranking ───────────────────────────────────────────
    reranker = _get_reranker()
    if reranker and len(mmr_results) > 1:
        try:
            pairs = [(query, text) for text, _, _ in mmr_results]
            scores = reranker.predict(pairs)
            ranked = sorted(
                zip([t for t, _, _ in mmr_results], scores, [p for _, _, p in mmr_results]),
                key=lambda x: x[1],
                reverse=True,
            )
            final_chunks = ranked[:top_k_final]
            logger.info("reranking_done", final_chunks=len(final_chunks))
        except Exception as e:
            logger.warning("reranking_failed", error=str(e))
            final_chunks = [(t, s, p) for t, s, p in mmr_results[:top_k_final]]
    else:
        final_chunks = [(t, s, p) for t, s, p in mmr_results[:top_k_final]]

    # ── 5. Format Context ────────────────────────────────────────────────────
    if not final_chunks:
        return ""

    context_parts = []
    for i, (text, score, payload) in enumerate(final_chunks):
        page_num = payload.get("page_num", "?")
        context_parts.append(
            f"[Chunk {i+1} | Page {page_num}]\n{text}"
        )

    return "\n\n---\n\n".join(context_parts)
