"""PDF Cypher Generator Agent.

Translates Natural Language questions into Cypher queries for the PDF Graph.
Supports:
- Page-level retrieval via TextChunks.
- Strategic Entity associations.
- Global thematic retrieval via CommunitySummaries.
"""
import structlog
from langchain_core.prompts import ChatPromptTemplate
from app.infrastructure.llm import get_llm
from app.domain.analysis.entities import AnalysisState
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

CYPHER_PROMPT = """You are a Neo4j Cypher export specializing in Document Knowledge Graphs.
Convert the user question into a VALID Cypher query based on the schema below.

SCHEMA:
Nodes:
- (d:DocumentSource {{source_id, topics, summary}})
- (t:TextChunk {{chunk_id, text, page_num, community_id}})
- (e:Entity {{name, type, pagerank_score}})
- (c:CommunitySummary {{community_id, text, source_id}})

Relationships:
- (t)-[:PART_OF_DOCUMENT]->(d)
- (e)-[:MENTIONED_IN]->(d)
- (t)-[:SIMILAR_TO]->(t2)
- (t)-[:MENTIONS]->(e)
- (c)-[:SUMMARIZES]->(t)

RULES:
1. ALWAYS filter by `source_id = $source_id`.
2. Return ONLY raw Cypher. No markdown. No comments.
3. For global/thematic questions, query (c:CommunitySummary).
4. For specific associations, follow the (t)-[:MENTIONS]->(e) or (t)-[:SIMILAR_TO]->(t) paths.
5. Use `pagerank_score` to prioritize the most central entities.
6. Use LIMIT 15 for result sets.

User Question: {question}
Conversation Context: {context}
"""

async def pdf_cypher_generator_agent(state: AnalysisState) -> dict:
    """Generates a Cypher query for the PDF Graph."""
    source_id = state.get("source_id")
    question = state.get("question")
    context = state.get("running_summary", "")
    
    logger.info("pdf_cypher_generator_started", source_id=source_id)
    
    prompt = ChatPromptTemplate.from_template(CYPHER_PROMPT)
    llm = get_llm(temperature=0, model_name=settings.LLM_MODEL_PDF)
    
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
        logger.error("pdf_cypher_generation_failed", error=str(e))
        return {"cypher_query": None}
