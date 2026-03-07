from langgraph.graph import StateGraph, START, END
from src.state import ASEState
from src.agents.researcher import researcher_node
from src.agents.coder import coder_node
from src.agents.qa import qa_node

def should_continue(state: ASEState) -> str:
    """
    Conditional routing logic after QA.
    If tests pass, end the graph. If they fail, go back to coder.
    """
    if state.get("test_passed", False):
        return "end"
    
    # Optional: safeguard to prevent infinite back-and-forth loops
    if state.get("validation_attempts", 0) >= 3:
        print("Max validation attempts reached. Exiting with failure.")
        return "end"
        
    return "coder"

def create_ase_graph():
    """
    Builds and compiles the main Dircted Acyclic Graph (DAG) for the ASE System.
    """
    # 1. Initialize StateGraph
    workflow = StateGraph(ASEState)
    
    # 2. Add Nodes
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("qa", qa_node)
    
    # 3. Add Edges
    workflow.add_edge(START, "researcher")
    workflow.add_edge("researcher", "coder")
    workflow.add_edge("coder", "qa")
    
    # Conditional Edges from QA
    workflow.add_conditional_edges(
        "qa",
        should_continue,
        {
            "coder": "coder",
            "end": END
        }
    )
    
    # Compile the graph
    graph = workflow.compile()
    return graph
