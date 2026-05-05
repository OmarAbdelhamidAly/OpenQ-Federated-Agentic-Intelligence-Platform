import structlog
import json
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from app.infrastructure.llm import get_llm
from app.infrastructure.config import settings
from app.domain.analysis.entities import AnalysisState
from app.infrastructure.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger(__name__)

async def memory_manager_agent(state: AnalysisState) -> Dict[str, Any]:
    """
    Manages the short-term state and extracts long-term facts/entities to Neo4j.
    """
    source_id = state.get("source_id")
    tenant_id = state.get("tenant_id", "default_tenant")
    user_id = state.get("user_id", "default_user")
    
    logger.info("memory_manager_agent_started", source_id=source_id)
    
    question_text = state.get("question", "")
    insight_report = state.get("insight_report", "")
    
    # 1. Update strict Short-Term Window (Last 4 turns only)
    current_history = state.get("chat_history") or []
    if question_text:
        current_history.append({"role": "user", "content": question_text})
    if insight_report:
        current_history.append({"role": "assistant", "content": insight_report})
        
    MAX_SHORT_TERM = 4
    new_history = current_history[-MAX_SHORT_TERM:] if len(current_history) > MAX_SHORT_TERM else current_history
    
    # 2. Extract and Store Long-Term Memory in Neo4j
    if question_text and insight_report:
        try:
            llm = get_llm(temperature=0, model=settings.LLM_MODEL_FAST)
            prompt = ChatPromptTemplate.from_messages([
                ("system", 
                 "You are an AI Memory Extractor. Extract the most important fact or insight from the conversation.\n"
                 "Output ONLY a valid JSON object with the following structure:\n"
                 "{\n"
                 '  "fact": "A concise summary of the insight or user intent",\n'
                 '  "entities": [{"name": "entity name", "type": "Concept|File|Term"}]\n'
                 "}"),
                ("user", f"User Question: {question_text}\nAssistant Response: {insight_report}")
            ])
            
            res = await prompt.pipe(llm).ainvoke({})
            content_str = str(res.content if hasattr(res, 'content') else res).strip()
            
            # Clean JSON if wrapped in markdown
            if content_str.startswith("```json"):
                content_str = content_str[7:-3]
            elif content_str.startswith("```"):
                content_str = content_str[3:-3]
                
            memory_data = json.loads(content_str.strip())
            fact = memory_data.get("fact", "")
            entities = memory_data.get("entities", [])
            
            if fact:
                db = Neo4jAdapter()
                query = """
                MERGE (t:Tenant {id: $tenant_id})
                MERGE (u:User {id: $user_id})
                MERGE (u)-[:BELONGS_TO_TENANT]->(t)
                
                MERGE (s:Session {source_id: $source_id})
                MERGE (s)-[:OWNED_BY]->(u)
                
                CREATE (m:MemoryFact {
                    id: randomUUID(),
                    text: $fact,
                    timestamp: timestamp(),
                    domain: 'analysis'
                })
                MERGE (s)-[:PRODUCED_MEMORY]->(m)
                
                WITH m, $entities AS ents
                UNWIND ents AS ent
                MERGE (e:Entity {name: ent.name})
                ON CREATE SET e.type = ent.type
                MERGE (m)-[:MENTIONS {relevance_score: 1.0}]->(e)
                """
                params = {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "source_id": source_id,
                    "fact": fact,
                    "entities": entities
                }
                await db.execute_cypher(query, params)
                logger.info("neo4j_agent_memory_saved", fact_length=len(fact), entities_count=len(entities))
                
        except Exception as e:
            logger.error("neo4j_agent_memory_extraction_failed", error=str(e))
    
    logger.info("memory_manager_agent_finished", history_length=len(new_history))
    
    return {
        "chat_history": new_history
    }
