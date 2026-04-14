import os
import hashlib
import shutil
import structlog

logger = structlog.get_logger(__name__)

# Base path for code chunk storage.
# Can be overridden via env var for persistent volume mounting.
CODE_STORE_BASE = os.getenv("CODE_STORE_PATH", "/data/code_chunks")


class CodeStore:
    """
    Lightweight filesystem store for code snippets.

    Design rationale
    ----------------
    Storing raw source code as Neo4j node properties bloats the graph DB
    with blob data it is not optimised for (property reads slow down even
    when not requested in RETURN clauses). Instead we persist each snippet
    as a small text file keyed by a deterministic chunk_id, and store only
    that ID in Neo4j. Code is loaded on-demand when an agent needs it.

    Directory layout
    ----------------
    {base_path}/
      {source_id}/
        {chunk_id}.txt   ← one file per function / class
    """

    def __init__(self, base_path: str = CODE_STORE_BASE):
        self.base_path = base_path

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def save(
        self,
        source_id: str,
        entity_type: str,
        name: str,
        code: str,
    ) -> str:
        """
        Persist *code* and return a deterministic chunk_id.

        The id is derived from (source_id, entity_type, name) so that
        re-ingesting the same codebase is idempotent — existing files are
        silently overwritten rather than accumulating duplicates.
        """
        chunk_id = self._make_chunk_id(source_id, entity_type, name)
        path = self._chunk_path(source_id, chunk_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(code)
        except OSError as exc:
            logger.warning(
                "code_store_write_failed",
                chunk_id=chunk_id,
                error=str(exc),
            )

        return chunk_id

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def load(self, source_id: str, chunk_id: str) -> str:
        """
        Return the stored code for *chunk_id*, or an empty string if not
        found (the file may have been cleaned up already).
        """
        path = self._chunk_path(source_id, chunk_id)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            logger.warning(
                "code_store_read_missing",
                source_id=source_id,
                chunk_id=chunk_id,
            )
            return ""

    def load_many(
        self, source_id: str, chunk_ids: list[str], max_chars: int = 3000
    ) -> list[dict]:
        """
        Load up to *max_chars* total characters across multiple chunks.
        Returns a list of {"chunk_id": ..., "code": ...} dicts.
        Used by the insight agent to enrich the LLM prompt.
        """
        snippets = []
        total = 0
        for cid in chunk_ids:
            if total >= max_chars:
                break
            code = self.load(source_id, cid)
            if not code:
                continue
            remaining = max_chars - total
            snippets.append({"chunk_id": cid, "code": code[:remaining]})
            total += min(len(code), remaining)
        return snippets

    # ------------------------------------------------------------------
    # Cleanup helpers
    # ------------------------------------------------------------------

    def delete_all(self, source_id: str) -> None:
        """
        Remove all stored chunks for *source_id*.
        Called at the start of a re-index to avoid stale files.
        """
        source_dir = os.path.join(self.base_path, source_id)
        if os.path.exists(source_dir):
            try:
                shutil.rmtree(source_dir)
                logger.info("code_store_cleaned", source_id=source_id)
            except OSError as exc:
                logger.warning(
                    "code_store_clean_failed",
                    source_id=source_id,
                    error=str(exc),
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_chunk_id(source_id: str, entity_type: str, name: str) -> str:
        """sha256-based 16-char deterministic ID."""
        raw = f"{source_id}:{entity_type}:{name}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _chunk_path(self, source_id: str, chunk_id: str) -> str:
        return os.path.join(self.base_path, source_id, f"{chunk_id}.txt")
