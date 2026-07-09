import os
import subprocess
from unittest.mock import patch

def test_preflight_timeout(tmp_path):
    """Test TimeoutExpired handling in preflight check."""
    from src.agents.tester import _preflight_syntax_check
    
    f = tmp_path / "valid.py"
    f.write_text("def hello(): pass")
    
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=10)
        err = _preflight_syntax_check(str(f))
        assert "timed out" in err

def test_preflight_generic_exception(tmp_path):
    """Test generic Exception handling in preflight check."""
    from src.agents.tester import _preflight_syntax_check
    
    f = tmp_path / "valid.py"
    f.write_text("def hello(): pass")
    
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("OS Level Error")
        err = _preflight_syntax_check(str(f))
        assert "Pre-flight check error: OS Level Error" in err

def test_tester_cleanup_exception(mock_state, run_metrics):
    """Test error handling during temporary preflight file cleanup."""
    from src.agents.tester import tester_node
    
    mock_state["test_script"] = "assert True\n"
    
    # We patch os.remove to raise an exception ONLY for the tmp cleanup
    original_remove = os.remove
    def mock_remove(path):
        if "test_fix.py" in path:
            raise Exception("Cannot remove file")
        original_remove(path)
        
    with patch("os.remove", side_effect=mock_remove), \
         patch("src.agents.tester.DockerSandbox") as mock_sandbox:
        mock_sandbox.return_value.run_test.return_value = {"exit_code": 0, "logs": "ok"}
        
        # Should not crash the node
        result = tester_node(mock_state, metrics=run_metrics)
        assert result["test_passed"] is True
