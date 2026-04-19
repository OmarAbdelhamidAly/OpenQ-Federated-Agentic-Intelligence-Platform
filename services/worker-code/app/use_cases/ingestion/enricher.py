import structlog
from typing import List, Optional, Dict
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from app.infrastructure.llm import get_llm
from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

class CodeEnricher:
    """
    Uses centralized LLM factory to generate technical summaries.
    Uses Gemini for high-quality embeddings.
    """
    def __init__(self):
        # 1. Initialize LLM via centralized factory
        try:
            self.llm = get_llm(temperature=0.1, model=settings.LLM_MODEL_CODE)
            self.enabled = True
        except Exception as e:
            logger.error("enricher_llm_init_failed", error=str(e))
            self.enabled = False

        # 2. Embeddings (Google text-embedding-004 is modern and cost-effective)
        if settings.GEMINI_API_KEY:
            self.embeddings_model = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=settings.GEMINI_API_KEY
            )
        else:
            self.embeddings_model = None
            logger.warning("embeddings_disabled_no_gemini_key")

        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert software architect. "
                       "Provide a concise, 1-2 sentence technical summary of the provided code's purpose. "
                       "Focus on what it does and its role in the system. "
                       "Output ONLY the summary text."),
            ("user", "Code:\n\n{code}")
        ])

        self.semantic_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an elite Software Architecture Ontology Mapper.\n"
                       "Your objective is to semantically classify an isolated block of code from an unknown repository. "
                       "The codebase could follow any architectural paradigm (Microservices, Monolithic, Event-Driven, MVC, Clean Architecture) or it could be unstructured Spaghetti code.\n\n"
                       "Analyze the code and deeply infer its semantic meaning, architectural role, and behavior. "
                       "Return a STRICT JSON object utilizing the following advanced ontology schema:\n"
                       "{\n"
                       "  \"summary\": \"A concise, technical explanation of what this block logic accomplishes.\",\n"
                       "  \"semantic_archetype\": \"Identify its core architectural nature. (Examples: 'Controller', 'Repository', 'DTO', 'Factory', 'EventPublisher', 'Middleware', 'GodObject', 'SpaghettiScript', 'Orchestrator', 'UI_Component').\",\n"
                       "  \"inferred_domain\": \"The business context. (Examples: 'Authentication', 'Billing', 'CoreSystem', 'Utility', 'Unknown_Context').\",\n"
                       "  \"execution_nature\": \"Classify how it handles state. (Examples: 'Pure_Function', 'State_Mutator', 'IO_Bound', 'Event_Driven', 'Procedural_Script').\",\n"
                       "  \"architectural_layer\": \"Inferred logical layer. (Examples: 'Presentation', 'Application/Service', 'Domain_Logic', 'Persistence', 'Network/API', 'Undefined/Mixed_Spaghetti').\",\n"
                       "  \"structural_health\": \"A qualitative gauge. (Examples: 'Clean/Cohesive', 'GodObject/HighCoupling', 'Boilerplate', 'Legacy_Script').\"\n"
                       "}"),
            ("user", "Code:\n\n{code}")
        ])

    async def summarize(self, code: str) -> Optional[str]:
        # Backward compatibility: extract only the summary string
        data = await self.semantic_summarize(code)
        return data.get("summary") if data else None

    async def semantic_summarize(self, code: str) -> Dict[str, str]:
        default_ontology = {
            "summary": "Unknown",
            "semantic_archetype": "Unknown",
            "inferred_domain": "Unknown",
            "execution_nature": "Unknown",
            "architectural_layer": "Unknown",
            "structural_health": "Unknown"
        }
        if not self.enabled or not self.llm or not code.strip():
            return default_ontology
        
        try:
            import json
            # Truncate very long code to avoid token limits
            truncated_code = code[:5000] 
            res = await self.semantic_prompt.pipe(self.llm).ainvoke({"code": truncated_code})
            
            content = str(res.content).strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            
            # Ensure all keys exist
            for key in default_ontology:
                if key not in data:
                    data[key] = "Unknown"
                    
            return data
        except Exception as e:
            logger.error("semantic_summarization_failed", error=str(e))
            return default_ontology

    async def embed(self, text: str) -> List[float]:
        if not self.embeddings_model or not text:
            return []
        
        try:
            return await self.embeddings_model.aembed_query(text)
        except Exception as e:
            logger.error("embedding_failed", error=str(e))
            return []

    async def summarize_file(self, content_summaries: List[str]) -> Optional[str]:
        """Summarize a file based on its component (class/function) summaries."""
        if not self.enabled or not content_summaries:
            return "General purpose source file."
        
        prompt = f"""
        You are a Technical Lead. Summarize the overall purpose of a source file based on the summaries of its classes and functions:
        
        COMPONENT SUMMARIES:
        {chr(10).join(content_summaries)}
        
        Provide a 1-sentence technical overview of the file's role.
        """
        try:
            res = await self.llm.ainvoke(prompt)
            return str(res.content).strip()
        except Exception:
            return None

    async def summarize_directory(self, file_summaries: List[str], dir_name: str) -> Dict[str, str]:
        """Summarize a directory's architectural role based on its files."""
        from app.modules.code.utils.taxonomy import CODE_ROLES
        if not self.enabled or not file_summaries:
            return {"summary": "General module", "domain": "General"}
        
        prompt = f"""
        You are a Software Architect. Define the architectural role of the directory '{dir_name}' based on the files it contains.
        
        FILE SUMMARIES:
        {chr(10).join(file_summaries[:20])}  # Limit for context window
        
        ROLES AVAILABLE: {list(CODE_ROLES.keys())}
        
        Respond with VALID JSON:
        {{
          "summary": "1-sentence architectural summary",
          "domain": "One of the ROLES AVAILABLE"
        }}
        """
        try:
            import json
            res = await self.llm.ainvoke(prompt)
            mapping = res.content
            if "```json" in mapping:
                mapping = mapping.split("```json")[1].split("```")[0].strip()
            data = json.loads(mapping)
            return data
        except Exception:
            return {"summary": f"Module containing {len(file_summaries)} files", "domain": "Business Logic"}
