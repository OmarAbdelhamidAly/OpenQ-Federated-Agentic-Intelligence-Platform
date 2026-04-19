"""Audio Cypher Generator Agent.

Translates Natural Language questions into Cypher queries for the Audio Conversation Graph.
Supports:
- Speaker-specific retrieval.
- Chronological context via SpeakerTurns.
- Global thematic retrieval via CommunitySummaries.
"""
import structlog
from langchain_core.prompts import ChatPromptTemplate
from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AudioAnalysisState
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

CYPHER_PROMPT = """You are a Neo4j Cypher expert specializing in Conversation Analysis Graphs.
Convert the user question into a VALID Cypher query based on the schema below.

SCHEMA:
Nodes:
- (a:AudioSource {{source_id, topics, tenant_id}})
- (s:Speaker {{speaker_id, name, source_id}})
- (t:SpeakerTurn {{chunk_id, text, start_time, community_id}})
- (e:Entity {{name, type}})
- (c:CommunitySummary {{community_id, text, source_id}})

Relationships:
- (s)-[:SPEAKS_IN]->(a)
- (s)-[:SPOKE]->(t)
- (t)-[:PART_OF]->(a)
- (e)-[:MENTIONED_IN]->(a)
- (c)-[:SUMMARIZES]->(t)

RULES:
1. ALWAYS filter by `source_id = $source_id`.
2. Return ONLY raw Cypher. No markdown. No comments.
3. For global/thematic questions, query (c:CommunitySummary).
4. For speaker-specific questions, use the (s)-[:SPOKE]->(t) path.
5. Use LIMIT 15 for result sets.

User Question: {question}
Conversation Context: {context}
"""

async def audio_cypher_generator_agent(state: AudioAnalysisState) -> dict:
    """Generates a Cypher query for the Audio Graph."""
    source_id = state.get("source_id")
    question = state.get("question")
    context = state.get("running_summary", "")
    
    logger.info("audio_cypher_generator_started", source_id=source_id)
    
    prompt = ChatPromptTemplate.from_template(CYPHER_PROMPT)
    llm = get_llm(temperature=0, model_name=settings.LLM_MODEL_AUDIO) # Assuming same LLM factory
    
    try:
        res = await prompt.pipe(llm).ainvoke({
            "question": question,
            "context": context
        })
        
        query = res.content.strip()
        # Clean potential markdown
        if "```" in query:
            query = query.split("```")[1]
            if query.lower().startswith("cypher"):
                query = query[6:].strip()
        
        return {
            "cypher_query": query,
            "cypher_params": {"source_id": source_id}
        }
    except Exception as e:
        logger.error("audio_cypher_generation_failed", error=str(e))
        return {"cypher_query": None}
