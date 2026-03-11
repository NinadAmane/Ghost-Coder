from langgraph.graph import StateGraph, START, END
from src.state import ASEState
from src.agents.researcher import researcher_node
from src.agents.coder import coder_node
from src.agents.tester import tester_node
from src.tools.github_tools import GitHubTool

def should_continue(state: ASEState) -> str:
    """
    Conditional edge: 
    If test passed, proceed to open PR and END.
    If test failed, loop back to Coder.
    """
    if state.get("test_passed"):
        
        # We can handle PR submission inline for simplicity as requested by Phase 3
        # Or you can extract it to another node, but inline meets requirement "Go to End (and open PR)"
        try:
            gh_tool = GitHubTool()
            pr_url = gh_tool.create_pull_request(
                repo_dir=state["repo_path"],
                branch_name=f"ghost-coder-fix",
                title="Automated Fix",
                body=f"Fixes {state['issue_url']}"
            )
            state["pr_url"] = pr_url
        except Exception as e:
            print(f"Failed to submit PR: {e}")
            
        return "end"
        
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
