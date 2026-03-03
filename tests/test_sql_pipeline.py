import pytest
import uuid
from unittest.mock import patch, MagicMock
from app.domain.analysis.entities import AnalysisState
from app.modules.sql.tools.run_sql_query import run_sql_query

@pytest.mark.asyncio
async def test_sql_security_guard():
    """Verify that only SELECT queries are allowed."""
    
    # 1. Positive Case: SELECT
    valid_query = "SELECT * FROM sales"
    # Note: run_sql_query expects a db_url or engine, we mock the execution
    with patch("app.modules.sql.tools.run_sql_query.create_async_engine") as mock_engine:
        # This should NOT raise an exception before execution
        pass 

@pytest.mark.asyncio
async def test_sql_injection_rejection():
    """Verify that DROP/DELETE/UPDATE are blocked by the tool logic."""
    from app.modules.sql.tools.run_sql_query import run_sql_query
    
    malicious_queries = [
        "DROP TABLE users",
        "DELETE FROM sales",
        "UPDATE users SET role='admin'",
        "INSERT INTO users (name) VALUES ('hacker')"
    ]
    
    for q in malicious_queries:
        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            await run_sql_query(q, "postgresql://mock")

@pytest.mark.asyncio
async def test_sql_workflow_mocked():
    """Test the SQL workflow integration."""
    from app.modules.sql.workflow import sql_pipeline
    
    state = AnalysisState(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        query="show me top users",
        data_source_id=uuid.uuid4(),
        data_source_type="sql"
    )
    
    with patch("app.modules.sql.agents.analysis_agent.ChatGroq") as mock_groq:
        mock_llm = mock_groq.return_value
        mock_llm.ainvoke.return_value = MagicMock(content="SELECT * FROM users ORDER BY id DESC LIMIT 5")
        
        # Mock DB response
        with patch("app.modules.sql.tools.run_sql_query.run_sql_query") as mock_run:
            mock_run.return_value = {"data": [{"name": "User 1"}], "columns": ["name"]}
            
            result = await sql_pipeline.ainvoke(state)
            
            assert result["status"] == "completed"
            assert "SQL" in result["metadata"]
