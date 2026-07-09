"""
Unit tests for the Tester agent node.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.agents.tester import tester_node, _preflight_syntax_check


class TestPreflightSyntaxCheck:
    """Tests for _preflight_syntax_check()."""

    def test_valid_syntax_returns_none(self, tmp_path):
        """Valid Python file passes the syntax check."""
        f = tmp_path / "valid.py"
        f.write_text("def hello():\n    return 42\n")
        assert _preflight_syntax_check(str(f)) is None

    def test_invalid_syntax_returns_error(self, tmp_path):
        """Invalid Python file returns an error string."""
        f = tmp_path / "invalid.py"
        f.write_text("def hello(\n")
        result = _preflight_syntax_check(str(f))
        assert result is not None
        assert len(result) > 0

    def test_nonexistent_file_returns_error(self):
        """Non-existent file returns an error."""
        result = _preflight_syntax_check("/nonexistent/path/file.py")
        assert result is not None


class TestTesterNode:
    """Tests for tester_node()."""

    def test_no_test_script_returns_failure(self, mock_state, run_metrics):
        """When coder provides no test script, tester reports failure."""
        mock_state["test_script"] = ""

        result = tester_node(mock_state, metrics=run_metrics)

        assert result["test_passed"] is False
        assert "No test script" in result["test_logs"]
        assert result["validation_attempts"] == 1

    @patch("src.agents.tester.DockerSandbox")
    def test_syntax_error_skips_docker(
        self, MockSandbox, mock_state, run_metrics
    ):
        """When code has syntax errors, Docker sandbox is never called."""
        mock_state["test_script"] = "def broken(\n"
        mock_state["updated_code"] = {}  # No source files, just bad test

        result = tester_node(mock_state, metrics=run_metrics)

        assert result["test_passed"] is False
        assert "SYNTAX CHECK FAILED" in result["test_logs"]
        # Docker should NOT have been instantiated for the test run
        MockSandbox.return_value.run_test.assert_not_called()

    @patch("src.agents.tester.DockerSandbox")
    def test_docker_success(
        self, MockSandbox, mock_state, run_metrics
    ):
        """When Docker sandbox returns exit_code 0, test passes."""
        mock_state["test_script"] = "assert 1 + 1 == 2\n"
        mock_state["updated_code"] = {}

        mock_sandbox = MockSandbox.return_value
        mock_sandbox.run_test.return_value = {
            "exit_code": 0,
            "logs": "All tests passed!",
        }

        result = tester_node(mock_state, metrics=run_metrics)

        assert result["test_passed"] is True
        assert result["test_logs"] == "All tests passed!"
        assert result["validation_attempts"] == 1

    @patch("src.agents.tester.ChatGroq")
    @patch("src.agents.tester.DockerSandbox")
    def test_docker_failure_gets_explanation(
        self, MockSandbox, MockChatGroq, mock_state, mock_llm_response, run_metrics
    ):
        """When tests fail, LLM is called to explain the failure."""
        mock_state["test_script"] = "assert 1 + 1 == 3\n"
        mock_state["updated_code"] = {}

        mock_sandbox = MockSandbox.return_value
        mock_sandbox.run_test.return_value = {
            "exit_code": 1,
            "logs": "AssertionError: assert 2 == 3",
        }

        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.return_value = mock_llm_response(
            "The assertion failed because 1+1=2, not 3."
        )

        result = tester_node(mock_state, metrics=run_metrics)

        assert result["test_passed"] is False
        assert "assertion failed" in result["test_explanation"].lower()

    @patch("src.agents.tester.DockerSandbox")
    def test_docker_unavailable(
        self, MockSandbox, mock_state, run_metrics
    ):
        """When Docker is not running, tester reports clear error."""
        mock_state["test_script"] = "assert True\n"
        mock_state["updated_code"] = {}

        MockSandbox.side_effect = Exception("Cannot connect to Docker daemon")

        result = tester_node(mock_state, metrics=run_metrics)

        assert result["test_passed"] is False
        assert "Docker" in result["test_explanation"]

    @patch("src.agents.tester.ChatGroq")
    @patch("src.agents.tester.DockerSandbox")
    def test_llm_explanation_failure_uses_raw_logs(
        self, MockSandbox, MockChatGroq, mock_state, run_metrics
    ):
        """When LLM explanation call fails, raw logs are used as fallback."""
        mock_state["test_script"] = "assert False\n"
        mock_state["updated_code"] = {}

        mock_sandbox = MockSandbox.return_value
        mock_sandbox.run_test.return_value = {
            "exit_code": 1,
            "logs": "AssertionError",
        }

        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = Exception("LLM rate limited")

        result = tester_node(mock_state, metrics=run_metrics)

        assert result["test_passed"] is False
        assert "AssertionError" in result["test_explanation"]

    @patch("src.agents.tester.DockerSandbox")
    def test_increments_validation_attempts(
        self, MockSandbox, mock_state, run_metrics
    ):
        """Validation attempts counter increments correctly."""
        mock_state["test_script"] = "assert True\n"
        mock_state["updated_code"] = {}
        mock_state["validation_attempts"] = 2

        mock_sandbox = MockSandbox.return_value
        mock_sandbox.run_test.return_value = {
            "exit_code": 0,
            "logs": "ok",
        }

        result = tester_node(mock_state, metrics=run_metrics)

        assert result["validation_attempts"] == 3
