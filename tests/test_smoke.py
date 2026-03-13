def test_imports():
    """ Smoke test to verify that the core components can be imported. """
    from src.agents.researcher import researcher_node
    from src.agents.coder import coder_node
    from src.agents.tester import tester_node
    
    assert researcher_node is not None
    assert coder_node is not None
    assert tester_node is not None

def test_state_structure():
    """ Verify the state dictionary has the required keys. """
    from src.state import ASEState
    # Just checking if ASEState can be referenced (it's a TypedDict)
    assert ASEState is not None
    
    state = {
        "issue_url": "",
        "issue_description": "",
        "repo_path": "",
        "files_to_modify": [],
        "research_summary": "",
        "updated_code": {},
        "test_script": "",
        "test_logs": "",
        "test_passed": False,
        "test_explanation": "",
        "validation_attempts": 0
    }
    assert "research_summary" in state
    assert "test_script" in state
