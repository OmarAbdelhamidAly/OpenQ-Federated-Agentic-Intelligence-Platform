"""Graph Knowledge Builder Agent — LangGraph Node.

Responsible strictly for building the relationships in the Neo4j Knowledge Graph.
Maps Participants and extracted Entities to the parent Audio Source.
"""
from __future__ import annotations
import structlog
from typing import Any, Dict
from app.domain.analysis.entities import AudioAnalysisState

logger = structlog.get_logger(__name__)


async def graph_knowledge_builder_agent(state: AudioAnalysisState) -> Dict[str, Any]:
    """Sync entities, speakers, and the core audio source to Neo4j."""
    if state.get("error"):
        return {}

    source_id = state.get("source_id", "")
    tenant_id = state.get("tenant_id", "")
    entities = state.get("entities", [])
    topics = state.get("topics", [])
    speakers_map = state.get("speakers_map", {})
    speaker_turns = state.get("speaker_turns", [])

    if not source_id or not tenant_id:
        return {}

    try:
        from app.infrastructure.neo4j_adapter import Neo4jAdapter
        neo4j = Neo4jAdapter()

        # 1. Create the root AudioSource metadata node
        await neo4j.run_query(
            """
            MERGE (a:AudioSource {source_id: $source_id})
            SET a.tenant_id = $tenant_id,
                a.pillar = 'audio',
                a.topics = $topics
            """,
            {"source_id": source_id, "tenant_id": tenant_id, "topics": topics},
        )

        # 2. Map Speakers to the Audio Source
        for speaker_id, speaker_name in speakers_map.items():
            await neo4j.run_query(
                """
                MERGE (s:Speaker {speaker_id: $speaker_id, source_id: $source_id})
                SET s.name = $name
                WITH s
                MATCH (a:AudioSource {source_id: $source_id})
                MERGE (s)-[:SPEAKS_IN]->(a)
                """,
                {"speaker_id": speaker_id, "source_id": source_id, "name": speaker_name},
            )

        # 3. Create SpeakerTurn chunks (The core of our GraphRAG)
        for turn in speaker_turns:
            chunk_id = turn.get("chunk_id")
            if not chunk_id:
                continue
                
            await neo4j.run_query(
                """
                MATCH (s:Speaker {speaker_id: $speaker_id, source_id: $source_id})
                MATCH (a:AudioSource {source_id: $source_id})
                MERGE (t:SpeakerTurn {chunk_id: $chunk_id})
                SET t.text = $text,
                    t.start_time = $start_time,
                    t.embedding = $embedding
                MERGE (s)-[:SPOKE]->(t)
                MERGE (t)-[:PART_OF]->(a)
                """,
                {
                    "chunk_id": chunk_id,
                    "speaker_id": turn.get("speaker_id", "SPEAKER_01"),
                    "source_id": source_id,
                    "text": turn.get("text", ""),
                    "start_time": turn.get("start_time", 0.0),
                    "embedding": turn.get("embedding", [])
                }
            )

        # 4. Map semantic Entities discovered inside the transcript
        for entity in entities[:20]:  # Cap at 20 critical entities to avoid graph clutter
            await neo4j.run_query(
                """
                MERGE (e:Entity {name: $name, type: $type})
                WITH e
                MATCH (a:AudioSource {source_id: $source_id})
                MERGE (e)-[:MENTIONED_IN]->(a)
                """,
                {
                    "name": entity.get("name", ""),
                    "type": entity.get("type", "Unknown"),
                    "source_id": source_id,
                },
            )

        # 5. Ensure Vector Index Exists for GDS
        await neo4j.run_query(
            """
            CREATE VECTOR INDEX audio_chunks IF NOT EXISTS 
            FOR (t:SpeakerTurn) 
            ON (t.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 768,
                `vector.similarity_function`: 'cosine'
            }}
            """
        )

        logger.info("audio_neo4j_synced", speakers=len(speakers_map), entities=len(entities), chunks=len(speaker_turns))

    except Exception as e:
        logger.warning("audio_neo4j_failed", error=str(e))

    return {} # Doesn't modify LangGraph State, just produces side effects in Neo4j
