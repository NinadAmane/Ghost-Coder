from langgraph.graph import StateGraph, START, END
from src.state import ASEState
from src.agents.researcher import researcher_node
from src.agents.coder import coder_node
from src.agents.tester import tester_node

def should_continue(state: ASEState) -> str:
    """ Loop back to coder if tests fail, up to 3 times. """
    if state.get("test_passed", False):
        return "end"
    
    if state.get("validation_attempts", 0) >= 3:
        print("Max validation attempts reached. Exiting.")
        return "end"
        
    return "coder"

def create_ase_graph():
    """ 3-Agent Loop: Researcher -> Coder -> Tester -> (Coder if fail) """
    workflow = StateGraph(ASEState)
    
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("tester", tester_node)
    
    workflow.add_edge(START, "researcher")
    workflow.add_edge("researcher", "coder")
    workflow.add_edge("coder", "tester")
    
    workflow.add_conditional_edges(
        "tester",
        should_continue,
        {
            "coder": "coder",
            "end": END
        }
    )
    
    return workflow.compile()
