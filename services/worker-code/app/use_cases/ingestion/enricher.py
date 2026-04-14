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

    async def summarize(self, code: str) -> Optional[str]:
        if not self.enabled or not self.llm or not code.strip():
            return None
        
        try:
            # Truncate very long code to avoid token limits
            truncated_code = code[:5000] 
            res = await self.summary_prompt.pipe(self.llm).ainvoke({"code": truncated_code})
            return str(res.content).strip()
        except Exception as e:
            logger.error("summarization_failed", error=str(e))
            return None

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
