import os
from unittest.mock import patch

def test_coder_basename_stripping(mock_state, run_metrics, tmp_repo, mock_llm_response):
    """Test that coder properly strips leading repo basename."""
    from src.agents.coder import coder_node
    
    repo_basename = os.path.basename(tmp_repo.rstrip(os.sep))
    file_path = f"{repo_basename}/src/app.py"
    
    mock_state["files_to_modify"] = [file_path]
    mock_state["research_summary"] = "fix it"
    
    fix_response = mock_llm_response("def add(a, b):\n    return a + b\n")
    test_response = mock_llm_response("assert True")
    
    with patch("src.agents.coder.ChatGroq") as MockChatGroq:
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = [fix_response, test_response]
        
        result = coder_node(mock_state, metrics=run_metrics)
        
        # It should have stripped the basename and written to the correct path
        assert "src/app.py" in result["updated_code"]

def test_coder_directory_traversal_active_guard(mock_state, run_metrics, tmp_repo, mock_llm_response, tmp_path):
    """Test that the traversal guard block at line 217 is explicitly hit."""
    from src.agents.coder import coder_node
    
    # We need a file that actually exists outside the repo so _read_local_file succeeds
    outside_file = tmp_path.parent / "outside.py"
    outside_file.write_text("outside code")
    
    # The relative path from tmp_repo to outside_file (e.g. "../outside.py")
    rel_path = os.path.relpath(str(outside_file), tmp_repo)
    
    mock_state["files_to_modify"] = [rel_path]
    mock_state["research_summary"] = "malicious fix"
    
    fix_response = mock_llm_response("hacked code")
    test_response = mock_llm_response("assert True")
    
    with patch("src.agents.coder.ChatGroq") as MockChatGroq:
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = [fix_response, test_response]
        
        result = coder_node(mock_state, metrics=run_metrics)
        
        # The traversal guard should have blocked it from updating
        assert rel_path not in result["updated_code"]
