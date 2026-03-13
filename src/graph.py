from langgraph.graph import StateGraph, START, END
from src.state import ASEState
from src.agents.researcher import researcher_node
from src.agents.coder import coder_node
from src.agents.tester import tester_node
from src.agents.submitter import submit_pr_node

def should_continue(state: ASEState) -> str:
    """
    Conditional edge: 
    If test passed, proceed to open PR node.
    If test failed, loop back to Coder.
    """
    if state.get("test_passed"):
        return "submit_pr"
        
    # Prevent infinite loops
    if len(state.get("error_history", [])) > 3:
        print("Max attempts reached. Halting.")
        return "end"
        
    return "coder"

def create_ase_graph():
    """Builds the 4-node LangGraph logic."""
    workflow = StateGraph(ASEState)
    
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("tester", tester_node)
    workflow.add_node("submit_pr", submit_pr_node)
    
    workflow.add_edge(START, "researcher")
    workflow.add_edge("researcher", "coder")
    workflow.add_edge("coder", "tester")
    workflow.add_edge("submit_pr", END)
    
    workflow.add_conditional_edges(
        "tester",
        should_continue,
        {
            "coder": "coder",
            "submit_pr": "submit_pr",
            "end": END
        }
    )
    
    return workflow.compile()
