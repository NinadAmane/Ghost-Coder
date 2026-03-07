import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from src.tools.docker_sandbox import DockerSandbox

@patch('src.tools.docker_sandbox.docker.from_env')
def test_detect_language_python(mock_env):
    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox = DockerSandbox()
        # No specific language files, should default to python
        lang_config = sandbox.detect_language(tmpdir)
        assert lang_config["language"] == "python"
        
@patch('src.tools.docker_sandbox.docker.from_env')
def test_detect_language_rust(mock_env):
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "Cargo.toml"), "w") as f:
            f.write("")
        sandbox = DockerSandbox()
        lang_config = sandbox.detect_language(tmpdir)
        assert lang_config["language"] == "rust"

@patch('src.tools.docker_sandbox.docker.from_env')
def test_run_tests_success(mock_docker_env):
    mock_client = MagicMock()
    mock_docker_env.return_value = mock_client
    
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b"Tests passed"
    mock_client.containers.run.return_value = mock_container
    
    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox = DockerSandbox()
        result = sandbox.run_tests(tmpdir)
        
        assert result["success"] is True
        assert result["logs"] == "Tests passed"
        mock_client.containers.run.assert_called_once()
