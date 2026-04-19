"""
RAG Quality Evaluator — Native Galileo-equivalent Metrics

Implements the three core chunking evaluation metrics WITHOUT requiring
any external paid service (Galileo, Arize, etc.):

  1. Chunk Relevance   — How much of the chunk relates to the query?
                         Model: cross-encoder/ms-marco-MiniLM-L-6-v2
                         Range: 0.0 → 1.0

  2. Chunk Attribution — Did this chunk actually influence the response?
                         Model: cross-encoder/nli-deberta-v3-small (NLI)
                         Output: "Attributed" | "Not Attributed" + confidence

  3. Chunk Utilization — What fraction of the chunk's text was used in
                         the response?
                         Model: Sentence-level NLI over chunk sentences
                         Range: 0.0 → 1.0

All three metrics are computed in a single call via `evaluate_retrieval()`,
mirroring Galileo Luna's single-inference-call efficiency.

Usage:
    evaluator = RAGEvaluator()
    result = await evaluator.evaluate_retrieval(
        query="What was Q3 revenue?",
        chunks=[{"text": "...", "chunk_id": "abc"}],
        response="The Q3 revenue was $12M based on the financial report."
    )
"""
from __future__ import annotations

import asyncio
import re
import structlog
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

logger = structlog.get_logger(__name__)


# ── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class ChunkEvaluation:
    """Evaluation result for a single retrieved chunk."""
    chunk_id: str
    chunk_text: str
    page_num: int
    element_type: str                    # Table | NarrativeText | Code | etc.

    # Metric 1 — Relevance
    relevance_score: float = 0.0         # 0→1, how relevant to query
    relevance_label: str = "Unknown"     # "High" | "Medium" | "Low"

    # Metric 2 — Attribution
    attributed: bool = False             # Did this chunk affect the response?
    attribution_confidence: float = 0.0  # 0→1 confidence in attribution

    # Metric 3 — Utilization
    utilization_score: float = 0.0       # 0→1, fraction of chunk used
    utilized_sentences: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class RetrievalEvaluation:
    """Aggregate evaluation for a full retrieval + generation cycle."""
    query: str
    total_chunks: int
    attributed_chunks: int               # Count of Attributed chunks
    not_attributed_chunks: int

    avg_relevance: float = 0.0           # Mean relevance across all chunks
    avg_utilization: float = 0.0         # Mean utilization of attributed chunks
    attribution_rate: float = 0.0        # % of retrieved chunks that were used

    chunks: List[ChunkEvaluation] = field(default_factory=list)

    # Actionable Diagnostics
    diagnosis: str = ""                  # Human-readable recommendation
    suggested_chunk_size: str = ""       # "reduce" | "increase" | "optimal"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "total_chunks": self.total_chunks,
            "attributed_chunks": self.attributed_chunks,
            "not_attributed_chunks": self.not_attributed_chunks,
            "avg_relevance": round(self.avg_relevance, 3),
            "avg_utilization": round(self.avg_utilization, 3),
            "attribution_rate": round(self.attribution_rate, 3),
            "diagnosis": self.diagnosis,
            "suggested_chunk_size": self.suggested_chunk_size,
            "chunks": [c.to_dict() for c in self.chunks],
        }


# ── Model Loader (Lazy, Singleton) ────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_cross_encoder_relevance():
    """
    Cross-encoder for Chunk Relevance scoring.
    Model: ms-marco-MiniLM-L-6-v2 (~35MB, very fast)
    Scores: query-document relevance
    """
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            max_length=512,
        )
        logger.info("relevance_cross_encoder_loaded")
        return model
    except ImportError:
        logger.warning("sentence_transformers_not_installed",
                        hint="pip install sentence-transformers")
        return None
    except Exception as e:
        logger.error("relevance_cross_encoder_load_failed", error=str(e))
        return None


@lru_cache(maxsize=1)
def _get_nli_model():
    """
    NLI Cross-encoder for Attribution & Utilization.
    Model: nli-deberta-v3-small (~180MB)
    Labels: contradiction | neutral | entailment
    """
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder(
            "cross-encoder/nli-deberta-v3-small",
            max_length=512,
        )
        logger.info("nli_cross_encoder_loaded")
        return model
    except ImportError:
        logger.warning("sentence_transformers_not_installed")
        return None
    except Exception as e:
        logger.error("nli_cross_encoder_load_failed", error=str(e))
        return None


# ── Core Evaluator Class ──────────────────────────────────────────────────────

class RAGEvaluator:
    """
    Production RAG Quality Evaluator.

    Computes Chunk Relevance, Attribution, and Utilization in a single
    pass, analogous to Galileo's Luna model family — but running entirely
    on-premises with no external API calls.
    """

    # Thresholds for label classification
    RELEVANCE_HIGH = 0.7
    RELEVANCE_MEDIUM = 0.4
    NLI_ENTAILMENT_THRESHOLD = 0.5      # probability above which = "Attributed"
    UTILIZATION_SENTENCE_THRESHOLD = 0.4 # entailment prob for sentence = "utilized"

    async def evaluate_retrieval(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        response: str,
    ) -> RetrievalEvaluation:
        """
        Main entry point. Evaluates all three metrics for a retrieval cycle.

        Args:
            query:    The user's original question.
            chunks:   List of retrieved chunks. Each dict must have:
                        - "text": str (the chunk content)
                        - "chunk_id": str
                        - "page_num": int (optional, defaults to 0)
                        - "element_type": str (optional)
            response: The LLM's generated response (insight_report).

        Returns:
            RetrievalEvaluation with per-chunk metrics and aggregate diagnostics.
        """
        if not chunks or not response:
            logger.warning("rag_evaluator_skipped_empty_input")
            return self._empty_evaluation(query)

        logger.info("rag_evaluation_started",
                    query=query[:60],
                    chunk_count=len(chunks))

        # Run all evaluations concurrently for speed
        chunk_texts = [c.get("text", "") for c in chunks]

        relevance_scores, attribution_results, utilization_scores = await asyncio.gather(
            self._batch_relevance(query, chunk_texts),
            self._batch_attribution(chunk_texts, response),
            self._batch_utilization(chunk_texts, response),
        )

        # ── Build per-chunk results ────────────────────────────────────────────
        evaluated_chunks: List[ChunkEvaluation] = []
        for i, chunk in enumerate(chunks):
            rel_score = relevance_scores[i]
            attr_bool, attr_conf = attribution_results[i]
            util_score, util_sents = utilization_scores[i]

            evaluated_chunks.append(ChunkEvaluation(
                chunk_id=chunk.get("chunk_id", f"chunk_{i}"),
                chunk_text=chunk.get("text", "")[:500],   # Store truncated for storage
                page_num=chunk.get("page_num", 0),
                element_type=chunk.get("element_type", "Unknown"),
                relevance_score=round(rel_score, 3),
                relevance_label=self._relevance_label(rel_score),
                attributed=attr_bool,
                attribution_confidence=round(attr_conf, 3),
                utilization_score=round(util_score, 3),
                utilized_sentences=util_sents[:3],         # Store top 3 utilized sentences
            ))

        # ── Aggregate metrics ──────────────────────────────────────────────────
        attributed = [c for c in evaluated_chunks if c.attributed]
        not_attributed = [c for c in evaluated_chunks if not c.attributed]

        avg_relevance = (
            sum(c.relevance_score for c in evaluated_chunks) / len(evaluated_chunks)
            if evaluated_chunks else 0.0
        )
        avg_utilization = (
            sum(c.utilization_score for c in attributed) / len(attributed)
            if attributed else 0.0
        )
        attribution_rate = len(attributed) / len(evaluated_chunks) if evaluated_chunks else 0.0

        diagnosis, suggestion = self._diagnose(
            avg_relevance, avg_utilization, attribution_rate, len(evaluated_chunks)
        )

        result = RetrievalEvaluation(
            query=query,
            total_chunks=len(evaluated_chunks),
            attributed_chunks=len(attributed),
            not_attributed_chunks=len(not_attributed),
            avg_relevance=avg_relevance,
            avg_utilization=avg_utilization,
            attribution_rate=attribution_rate,
            chunks=evaluated_chunks,
            diagnosis=diagnosis,
            suggested_chunk_size=suggestion,
        )

        logger.info("rag_evaluation_complete",
                    total=len(evaluated_chunks),
                    attributed=len(attributed),
                    avg_relevance=round(avg_relevance, 3),
                    avg_utilization=round(avg_utilization, 3),
                    attribution_rate=round(attribution_rate, 3))

        return result

    # ── Metric 1: Chunk Relevance ─────────────────────────────────────────────

    async def _batch_relevance(
        self, query: str, chunk_texts: List[str]
    ) -> List[float]:
        """
        Compute query-chunk relevance using a Cross-Encoder.
        Returns normalized scores in [0, 1].
        """
        if not chunk_texts:
            return []

        relevance_model = _get_cross_encoder_relevance()
        if relevance_model is None:
            # Graceful fallback: use keyword overlap
            return [self._keyword_overlap(query, t) for t in chunk_texts]

        try:
            pairs = [(query, text[:400]) for text in chunk_texts]
            # Cross-encoder returns raw logits for ms-marco — sigmoid to normalize
            scores = await asyncio.to_thread(relevance_model.predict, pairs)
            import math
            normalized = [1 / (1 + math.exp(-float(s))) for s in scores]
            return normalized
        except Exception as e:
            logger.error("relevance_scoring_failed", error=str(e))
            return [self._keyword_overlap(query, t) for t in chunk_texts]

    # ── Metric 2: Chunk Attribution ───────────────────────────────────────────

    async def _batch_attribution(
        self, chunk_texts: List[str], response: str
    ) -> List[Tuple[bool, float]]:
        """
        Determine attribution using NLI: chunk → response.
        "Attributed" = the chunk entails part of the response.

        Strategy: NLI(premise=response_sentence, hypothesis=chunk)
        If any response sentence is entailed by the chunk → Attributed.
        """
        if not chunk_texts or not response:
            return [(False, 0.0)] * len(chunk_texts)

        nli_model = _get_nli_model()
        if nli_model is None:
            return [self._fallback_attribution(t, response) for t in chunk_texts]

        # Split response into sentences for targeted NLI
        response_sentences = _split_sentences(response)[:8]  # Top 8 sentences

        try:
            results = []
            for chunk_text in chunk_texts:
                # NLI: premise=chunk, hypothesis=each response sentence
                pairs = [(chunk_text[:400], sent) for sent in response_sentences]
                scores = await asyncio.to_thread(nli_model.predict, pairs,
                                                  apply_softmax=True)
                # scores shape: (n_sentences, 3) → [contradiction, neutral, entailment]
                # Take max entailment probability across all response sentences
                max_entailment = max(float(s[2]) for s in scores) if len(scores) > 0 else 0.0
                attributed = max_entailment >= self.NLI_ENTAILMENT_THRESHOLD
                results.append((attributed, max_entailment))
            return results
        except Exception as e:
            logger.error("attribution_scoring_failed", error=str(e))
            return [self._fallback_attribution(t, response) for t in chunk_texts]

    # ── Metric 3: Chunk Utilization ───────────────────────────────────────────

    async def _batch_utilization(
        self, chunk_texts: List[str], response: str
    ) -> List[Tuple[float, List[str]]]:
        """
        Measure what fraction of each chunk's sentences were used in the response.
        
        For each sentence in the chunk, we compute NLI(premise=sentence, hypothesis=response).
        Utilization = (sentences with entailment prob > threshold) / total sentences.
        """
        if not chunk_texts or not response:
            return [(0.0, [])] * len(chunk_texts)

        nli_model = _get_nli_model()
        if nli_model is None:
            return [(0.0, [])] * len(chunk_texts)

        try:
            results = []
            for chunk_text in chunk_texts:
                sentences = _split_sentences(chunk_text)
                if not sentences:
                    results.append((0.0, []))
                    continue

                # NLI: premise=each chunk sentence, hypothesis=response (truncated)
                pairs = [(sent, response[:400]) for sent in sentences]
                scores = await asyncio.to_thread(nli_model.predict, pairs,
                                                  apply_softmax=True)

                utilized_sents = [
                    sentences[j]
                    for j, s in enumerate(scores)
                    if float(s[2]) >= self.UTILIZATION_SENTENCE_THRESHOLD
                ]

                utilization = len(utilized_sents) / len(sentences)
                results.append((utilization, utilized_sents))
            return results
        except Exception as e:
            logger.error("utilization_scoring_failed", error=str(e))
            return [(0.0, [])] * len(chunk_texts)

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def _diagnose(
        self,
        avg_relevance: float,
        avg_utilization: float,
        attribution_rate: float,
        total_chunks: int,
    ) -> Tuple[str, str]:
        """
        Generate actionable diagnosis based on the three metrics.
        Mirrors Galileo's recommendations from the book.
        """
        issues = []
        suggestion = "optimal"

        # ── Rule 1: Many Not-Attributed chunks → retrieve fewer ────────────────
        if attribution_rate < 0.4:
            issues.append(
                f"Only {attribution_rate:.0%} of retrieved chunks influenced the response. "
                "Consider reducing the retrieval `k` parameter to retrieve fewer, "
                "higher-quality chunks."
            )
            suggestion = "reduce_k"

        # ── Rule 2: Low Utilization → chunks too large ─────────────────────────
        if avg_utilization < 0.35 and attribution_rate > 0.3:
            issues.append(
                f"Average chunk utilization is {avg_utilization:.0%}. "
                "Large portions of each retrieved chunk are being ignored. "
                "Consider reducing chunk_size to improve precision."
            )
            suggestion = "reduce"

        # ── Rule 3: Low Relevance → retrieval quality issue ────────────────────
        if avg_relevance < 0.35:
            issues.append(
                f"Average chunk relevance is {avg_relevance:.0%}. "
                "Retrieved chunks may not match the query well. "
                "Consider upgrading the embedding model or improving query expansion."
            )
            if suggestion == "optimal":
                suggestion = "improve_embeddings"

        # ── Rule 4: High Utilization + High Attribution → chunks may be too small ─
        if avg_utilization > 0.85 and attribution_rate > 0.8 and total_chunks < 5:
            issues.append(
                "Very high utilization with few retrieved chunks suggests chunks may "
                "be too small. Consider increasing chunk_size to provide more context."
            )
            suggestion = "increase"

        if not issues:
            diagnosis = (
                f"✅ RAG pipeline performing well. "
                f"Attribution: {attribution_rate:.0%}, "
                f"Relevance: {avg_relevance:.0%}, "
                f"Utilization: {avg_utilization:.0%}."
            )
        else:
            diagnosis = " | ".join(issues)

        return diagnosis, suggestion

    # ── Utility Helpers ───────────────────────────────────────────────────────

    def _relevance_label(self, score: float) -> str:
        if score >= self.RELEVANCE_HIGH:
            return "High"
        if score >= self.RELEVANCE_MEDIUM:
            return "Medium"
        return "Low"

    def _keyword_overlap(self, query: str, text: str) -> float:
        """Cheap fallback relevance when model is unavailable."""
        q_words = set(query.lower().split())
        t_words = set(text.lower().split())
        if not q_words:
            return 0.0
        return len(q_words & t_words) / len(q_words)

    def _fallback_attribution(self, chunk: str, response: str) -> Tuple[bool, float]:
        """Cheap fallback attribution using n-gram overlap."""
        chunk_words = set(chunk.lower().split())
        resp_words = set(response.lower().split())
        if not chunk_words:
            return (False, 0.0)
        overlap = len(chunk_words & resp_words) / len(chunk_words)
        return (overlap > 0.15, overlap)

    def _empty_evaluation(self, query: str) -> RetrievalEvaluation:
        return RetrievalEvaluation(
            query=query,
            total_chunks=0,
            attributed_chunks=0,
            not_attributed_chunks=0,
            diagnosis="No chunks or response provided for evaluation.",
        )


# ── Text Utilities ────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> List[str]:
    """Split text into sentences for sentence-level NLI."""
    # Simple but effective sentence splitter
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    # Filter out very short or empty sentences
    return [s.strip() for s in sentences if len(s.strip()) > 15]


# ── Module-level singleton ────────────────────────────────────────────────────

_evaluator_instance: Optional[RAGEvaluator] = None


def get_evaluator() -> RAGEvaluator:
    """Get or create the singleton RAGEvaluator instance."""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = RAGEvaluator()
    return _evaluator_instance
