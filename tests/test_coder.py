import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from src.agents.coder import coder_node
from src.state import ASEState

def test_coder_node_valid_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        state: ASEState = {"repo_path": tmpdir, "research_summary": "Fix this."}
        
        mock_response = MagicMock()
        mock_response.content = '```json\n{"valid_file.py": "print(\'hello\')"}\n```'
        
        with patch('src.agents.coder.ChatGroq') as MockGroq:
            mock_llm = MockGroq.return_value
            mock_llm.invoke.return_value = mock_response
            
            result = coder_node(state)
            
            # Check file was written
            assert os.path.exists(os.path.join(tmpdir, "valid_file.py"))
            with open(os.path.join(tmpdir, "valid_file.py")) as f:
                assert f.read() == "print('hello')"

def test_coder_node_path_traversal():
    with tempfile.TemporaryDirectory() as tmpdir:
        state: ASEState = {"repo_path": tmpdir, "research_summary": "Fix this."}
        
        mock_response = MagicMock()
        # Attempt traversal
        mock_response.content = '```json\n{"../outside.py": "malicious"}\n```'
        
        with patch('src.agents.coder.ChatGroq') as MockGroq:
            mock_llm = MockGroq.return_value
            mock_llm.invoke.return_value = mock_response
            
            result = coder_node(state)
            
            # Check file was NOT written outside
            outside_path = os.path.abspath(os.path.join(tmpdir, "../outside.py"))
            assert not os.path.exists(outside_path)
            
def test_coder_node_absolute_path_traversal():
    with tempfile.TemporaryDirectory() as tmpdir:
        state: ASEState = {"repo_path": tmpdir, "research_summary": "Fix this."}
        
        mock_response = MagicMock()
        # Attempt absolute path
        mock_response.content = '```json\n{"/etc/passwd": "malicious"}\n```'
        
        with patch('src.agents.coder.ChatGroq') as MockGroq:
            mock_llm = MockGroq.return_value
            mock_llm.invoke.return_value = mock_response
            
            result = coder_node(state)
            
            # Should be written inside tmpdir, stripping the leading /
            assert os.path.exists(os.path.join(tmpdir, "etc/passwd"))
