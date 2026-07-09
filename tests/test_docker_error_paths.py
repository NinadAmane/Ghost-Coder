import os
from unittest.mock import patch, MagicMock

import pytest

from src.tools.docker_sandbox import DockerSandbox

def test_container_kill_exception_on_timeout(tmp_path):
    """If container kill fails during a timeout, it doesn't crash the sandbox."""
    with patch("src.tools.docker_sandbox.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        
        mock_container = MagicMock()
        # Trigger timeout
        mock_container.wait.side_effect = Exception("ReadTimeout")
        # Trigger exception on kill
        mock_container.kill.side_effect = Exception("Cannot kill container")
        
        mock_client.containers.run.return_value = mock_container
        
        sandbox = DockerSandbox()
        result = sandbox.run_test(str(tmp_path), "pass", timeout=1)
        
        assert result["exit_code"] == 1
        assert "timed out" in result["logs"].lower()

def test_generic_sandbox_exception(tmp_path):
    """If docker.run throws an unexpected generic error, it is caught."""
    with patch("src.tools.docker_sandbox.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        
        # Need to provide a valid Exception class for the except block to evaluate
        mock_docker.errors.ImageNotFound = type("ImageNotFound", (Exception,), {})
        
        mock_client.containers.run.side_effect = Exception("Unexpected Daemon Crash")
        
        sandbox = DockerSandbox()
        result = sandbox.run_test(str(tmp_path), "pass")
        
        assert result["exit_code"] == 1
        assert "Unexpected Daemon Crash" in result["logs"]

def test_container_remove_exception(tmp_path):
    """If removing the container in finally block fails, logs warning but doesn't crash."""
    with patch("src.tools.docker_sandbox.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"ok"
        mock_container.remove.side_effect = Exception("Removal failed")
        
        mock_client.containers.run.return_value = mock_container
        
        sandbox = DockerSandbox()
        result = sandbox.run_test(str(tmp_path), "pass")
        
        assert result["exit_code"] == 0

def test_test_file_remove_exception(tmp_path):
    """If deleting the temp test script fails, it logs warning but doesn't crash."""
    with patch("src.tools.docker_sandbox.docker") as mock_docker, \
         patch("os.remove") as mock_remove:
        
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"ok"
        mock_client.containers.run.return_value = mock_container
        
        # Trigger exception on file removal
        mock_remove.side_effect = Exception("Permission denied")
        
        sandbox = DockerSandbox()
        result = sandbox.run_test(str(tmp_path), "pass")
        
        assert result["exit_code"] == 0
