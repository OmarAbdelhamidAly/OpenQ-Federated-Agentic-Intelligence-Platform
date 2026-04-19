from __future__ import annotations
import re
from typing import Any, Dict, List, Set


class SemanticSchemaSelector:
    """Filters large database schemas to only relevant tables for a given query.

    Uses heuristic-based semantic matching + multi-hop FK expansion to ensure
    all tables needed for JOINs are always included.
    """

    @staticmethod
    def select_tables(schema_summary: Dict[str, Any], query: str, top_k: int = 10) -> Dict[str, Any]:
        """Return a filtered version of the schema summary.

        Steps:
        1. Exact/Partial match on table and column names against query terms.
        2. 2-hop FK expansion to include bridge/intersection tables.
        3. Fallback to full schema if nothing is selected.
        """
        if not schema_summary.get("tables") or len(schema_summary["tables"]) <= top_k:
            return schema_summary

        query = query.lower().strip()
        all_fks = schema_summary.get("foreign_keys", [])
        selected_table_names: Set[str] = set()

        # ─── LOCAL EMBEDDING ENGINE FOR FAST EXACT/SYNONYMOUS MATCHING ───
        try:
            from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
            import numpy as np
            
            # Using intfloat/multilingual-e5-large is great, but default FastEmbed is very fast
            embedder = FastEmbedEmbeddings()
            
            # Prepare table text for embedding
            table_documents = []
            for t in schema_summary["tables"]:
                t_name = t["table"]
                t_domain = t.get("domain", "")
                t_summary = t.get("summary", "")
                
                # Compress columns into text
                cols_str = ", ".join([c["name"] for c in t.get("columns", [])])
                
                # The text representation includes semantics we extracted via Profiler
                doc = f"Table: {t_name}. Domain: {t_domain}. Summary: {t_summary}. Columns: {cols_str}"
                table_documents.append((t_name, doc))
                
            # Embed all and the query
            query_vec = embedder.embed_query(query)
            table_docs_text = [doc for _, doc in table_documents]
            table_vecs = embedder.embed_documents(table_docs_text)
            
            # Score
            intent_vector = np.array(query_vec)
            scored_tables = []
            for idx, vec in enumerate(table_vecs):
                e_vec = np.array(vec)
                score = np.dot(intent_vector, e_vec) / (np.linalg.norm(intent_vector) * np.linalg.norm(e_vec))
                scored_tables.append((score, table_documents[idx][0]))
                
            # Sort and take top_k
            scored_tables.sort(key=lambda x: x[0], reverse=True)
            for score, t_name in scored_tables[:top_k]:
                # Dynamic Thresholding: Only take matches that are somewhat relevant
                if score > 0.4:  
                    selected_table_names.add(t_name)
                    
        except Exception as e:
            # Fallback to legacy keyword search if embeddings fail
            import re
            query_terms = set(re.findall(r"\w+", query))
            for t in schema_summary["tables"]:
                t_name = t["table"].lower()
                if any(term in t_name for term in query_terms):
                    selected_table_names.add(t["table"])
                    continue
                for c in t["columns"]:
                    c_name = c["name"].lower()
                    if any(term == c_name or term in c_name for term in query_terms):
                        selected_table_names.add(t["table"])
                        break

        # Phase 2: Multi-hop FK expansion (2 hops)
        # This ensures bridge/intersection tables are never dropped.
        # Example: Customer selected → Invoice added (hop 1) → InvoiceLine added (hop 2)
        for _hop in range(2):
            expansion: Set[str] = set()
            for fk in all_fks:
                if fk["from_table"] in selected_table_names:
                    expansion.add(fk["to_table"])
                if fk["to_table"] in selected_table_names:
                    expansion.add(fk["from_table"])
            selected_table_names.update(expansion)

        # Reconstruct filtered summary preserving original table order
        filtered_tables = [t for t in schema_summary["tables"] if t["table"] in selected_table_names]

        # Fallback: if nothing was matched, return entire schema
        if not filtered_tables:
            return schema_summary

        return {
            **schema_summary,
            "tables": filtered_tables,
            "filtered": True,
            "original_table_count": len(schema_summary["tables"]),
            "selected_tables": list(selected_table_names),
        }


schema_selector = SemanticSchemaSelector()
