"""Team 2: SQL Engineering Workflow Template.

Everything in this module is for the SQL Squad to build from scratch.
You MUST adhere to the AnalysisState contract for inputs and outputs.
"""

from langgraph.graph import StateGraph, END
from app.domain.analysis.entities import AnalysisState

def sql_entry_node(state: AnalysisState) -> AnalysisState:
    """Entry point for the SQL pipeline."""
    # TODO: Build your agents and tools here!
    return state

# Define the graph
workflow = StateGraph(AnalysisState)
workflow.add_node("entry", sql_entry_node)
workflow.set_entry_point("entry")
workflow.add_edge("entry", END)

# Compile the graph
sql_pipeline = workflow.compile()
