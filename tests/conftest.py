"""
Shared fixtures for Ghost Coder test suite.
"""

import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.metrics import RunMetrics


@pytest.fixture
def mock_state(tmp_repo):
    """Returns a fully populated ASEState dict with a real temp repo."""
    return {
        "issue_url": "https://github.com/testowner/testrepo/issues/42",
        "issue_description": "Bug: function returns wrong value\n\nThe add() function subtracts instead of adding.",
        "repo_path": tmp_repo,
        "github_token": "fake-gh-token",
        "groq_api_key": "fake-groq-key",
        "files_to_modify": [],
        "research_summary": "",
        "updated_code": {},
        "test_script": "",
        "test_logs": "",
        "test_passed": False,
        "test_explanation": "",
        "validation_attempts": 0,
    }


@pytest.fixture
def tmp_repo(tmp_path):
    """
    Creates a temporary directory with a sample Python file and
    initializes it as a git repo. Returns the path.
    """
    # Create sample file
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    app_file = src_dir / "app.py"
    app_file.write_text(
        "def add(a, b):\n"
        "    return a - b  # BUG: should be a + b\n",
        encoding="utf-8",
    )

    # Create a requirements.txt
    (tmp_path / "requirements.txt").write_text("requests>=2.28.0\n")

    # Initialize git repo (needed by some tools)
    subprocess.run(
        ["git", "init"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "add", "."],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c", "user.name=Test",
            "-c", "user.email=test@test.com",
            "commit",
            "-m",
            "initial",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )

    return str(tmp_path)


@pytest.fixture
def run_metrics():
    """Returns a fresh RunMetrics instance."""
    m = RunMetrics()
    m.start_run()
    return m


@pytest.fixture
def mock_llm_response():
    """Factory for creating mock LLM responses with token usage metadata."""

    def _make(content: str, prompt_tokens: int = 10, completion_tokens: int = 20):
        resp = MagicMock()
        resp.content = content
        resp.response_metadata = {
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        }
        return resp

    return _make
