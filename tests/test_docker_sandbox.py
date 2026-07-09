"""
Unit tests for DockerSandbox.
"""

from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from src.tools.docker_sandbox import DockerSandbox


class TestDockerSandbox:
    """Tests for DockerSandbox."""

    @patch("src.tools.docker_sandbox.docker")
    def test_run_test_success(self, mock_docker_module, tmp_path):
        """Successful container execution returns exit_code 0."""
        mock_client = MagicMock()
        mock_docker_module.from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"All tests passed!"
        mock_client.containers.run.return_value = mock_container

        sandbox = DockerSandbox()
        result = sandbox.run_test(
            str(tmp_path), "assert True\n", timeout=30
        )

        assert result["exit_code"] == 0
        assert result["logs"] == "All tests passed!"
        mock_container.remove.assert_called_once_with(force=True)

    @patch("src.tools.docker_sandbox.docker")
    def test_run_test_docker_unavailable(self, mock_docker_module):
        """When Docker daemon is not running, initialization raises."""
        mock_docker_module.from_env.side_effect = Exception(
            "Cannot connect to Docker daemon"
        )

        with pytest.raises(Exception, match="Cannot connect"):
            DockerSandbox()

    @patch("src.tools.docker_sandbox.docker")
    def test_run_test_timeout(self, mock_docker_module, tmp_path):
        """Container timeout returns error dict."""
        mock_client = MagicMock()
        mock_docker_module.from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_container.wait.side_effect = Exception("ReadTimeout")
        mock_client.containers.run.return_value = mock_container

        sandbox = DockerSandbox()
        result = sandbox.run_test(
            str(tmp_path), "import time; time.sleep(999)\n", timeout=1
        )

        assert result["exit_code"] == 1
        assert "timed out" in result["logs"].lower()

    @patch("src.tools.docker_sandbox.docker")
    def test_cleanup_on_failure(self, mock_docker_module, tmp_path):
        """Container is removed even when execution fails."""
        mock_client = MagicMock()
        mock_docker_module.from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 1}
        mock_container.logs.return_value = b"Error occurred"
        mock_client.containers.run.return_value = mock_container

        sandbox = DockerSandbox()
        sandbox.run_test(str(tmp_path), "assert False\n")

        mock_container.remove.assert_called_once_with(force=True)

    @patch("src.tools.docker_sandbox.docker")
    def test_image_not_found(self, mock_docker_module, tmp_path):
        """Handles docker.errors.ImageNotFound gracefully."""
        mock_client = MagicMock()
        mock_docker_module.from_env.return_value = mock_client
        mock_docker_module.errors.ImageNotFound = type(
            "ImageNotFound", (Exception,), {}
        )
        mock_client.containers.run.side_effect = (
            mock_docker_module.errors.ImageNotFound("not found")
        )

        sandbox = DockerSandbox()
        result = sandbox.run_test(str(tmp_path), "assert True\n")

        assert result["exit_code"] == 1
        assert "not found" in result["logs"].lower()

    @patch("src.tools.docker_sandbox.docker")
    def test_default_timeout(self, mock_docker_module):
        """Default timeout is 120 seconds."""
        mock_docker_module.from_env.return_value = MagicMock()
        sandbox = DockerSandbox()
        assert sandbox.DEFAULT_TIMEOUT_SECONDS == 120
