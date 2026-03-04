"""Team 1: CSV Analysis Workflow Template.

Everything in this module is for the CSV Squad to build from scratch.
You MUST adhere to the AnalysisState contract for inputs and outputs.
"""

from langgraph.graph import StateGraph, END
from app.domain.analysis.entities import AnalysisState

def csv_entry_node(state: AnalysisState) -> AnalysisState:
    """Entry point for the CSV pipeline."""
    # TODO: Build your agents and tools here!
    return state

# Define the graph
workflow = StateGraph(AnalysisState)
workflow.add_node("entry", csv_entry_node)
workflow.set_entry_point("entry")
workflow.add_edge("entry", END)

# Compile the graph
csv_pipeline = workflow.compile()
