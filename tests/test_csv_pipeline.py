import pytest
import uuid
from unittest.mock import patch, MagicMock
from app.domain.analysis.entities import AnalysisState
from app.modules.csv.workflow import csv_pipeline

@pytest.mark.asyncio
async def test_csv_workflow_mocked():
    """Test the CSV workflow cycle with mocked LLM."""
    
    # 1. Setup State
    initial_state = AnalysisState(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        query="What is the average sales?",
        data_source_id=uuid.uuid4(),
        data_source_type="csv",
        file_path="/tmp/test.csv"
    )

    # 2. Mock ALL Agents in the CSV pipeline
    with patch("app.modules.csv.agents.analysis_agent.ChatGroq") as mock_groq:
        # Configure mock to return valid pandas code
        mock_llm = mock_groq.return_value
        mock_llm.ainvoke.return_value = MagicMock(content="df['sales'].mean()")
        
        # 3. Execute Workflow via compiled graph
        # We use csv_pipeline directly
        
        # We need to mock tools as well if they touch the filesystem
        with patch("app.modules.csv.tools.run_pandas_query.pd.read_csv") as mock_read:
            import pandas as pd
            mock_read.return_value = pd.DataFrame({"sales": [10, 20, 30]})
            
            result = await csv_pipeline.ainvoke(initial_state)
            
            # 4. Assertions
            assert "result_summary" in result
            assert result["status"] == "completed"
            assert "chart_json" in result
