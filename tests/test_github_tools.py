"""
Unit tests for GitHubTool and URL parsing.
"""

import os
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from src.tools.github_tools import GitHubTool, _parse_issue_url


class TestParseIssueUrl:
    """Tests for _parse_issue_url()."""

    def test_valid_url(self):
        owner, repo, num = _parse_issue_url(
            "https://github.com/octocat/hello-world/issues/42"
        )
        assert owner == "octocat"
        assert repo == "hello-world"
        assert num == 42

    def test_valid_url_with_trailing_slash(self):
        owner, repo, num = _parse_issue_url(
            "https://github.com/octocat/hello-world/issues/42/"
        )
        assert owner == "octocat"
        assert repo == "hello-world"
        assert num == 42

    def test_malformed_url_raises(self):
        with pytest.raises(ValueError, match="Malformed"):
            _parse_issue_url("https://github.com/octocat")

    def test_non_numeric_issue_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            _parse_issue_url(
                "https://github.com/owner/repo/issues/abc"
            )

    def test_completely_wrong_url_raises(self):
        with pytest.raises(ValueError):
            _parse_issue_url("not-a-url")


class TestGitHubToolReadFile:
    """Tests for GitHubTool.read_file()."""

    def test_reads_text_file(self, tmp_repo):
        tool = GitHubTool(token="fake")
        content = tool.read_file(tmp_repo, "src/app.py")
        assert "def add" in content

    def test_file_not_found(self, tmp_repo):
        tool = GitHubTool(token="fake")
        result = tool.read_file(tmp_repo, "nonexistent.py")
        assert result == "File not found."

    def test_binary_file_handled(self, tmp_path):
        """Binary files return a clear message instead of crashing."""
        binary_file = tmp_path / "image.bin"
        binary_file.write_bytes(bytes(range(256)))
        tool = GitHubTool(token="fake")
        result = tool.read_file(str(tmp_path), "image.bin")
        assert "Binary file" in result or "Error" in result


class TestGitHubToolListFilesTree:
    """Tests for GitHubTool.list_files_tree()."""

    def test_returns_tree_string(self, tmp_repo):
        tool = GitHubTool(token="fake")
        tree = tool.list_files_tree(tmp_repo)
        assert "src/" in tree or "app.py" in tree
        assert ".git" not in tree  # .git should be filtered

    def test_empty_directory(self, tmp_path):
        tool = GitHubTool(token="fake")
        tree = tool.list_files_tree(str(tmp_path))
        assert "./" in tree


class TestGitHubToolFetchIssue:
    """Tests for GitHubTool.fetch_issue_details()."""

    def test_no_token_returns_error(self):
        tool = GitHubTool(token=None)
        # Also clear env var to prevent fallback
        with patch.dict(os.environ, {}, clear=True):
            tool2 = GitHubTool(token=None)
            tool2.client = None
            result = tool2.fetch_issue_details(
                "https://github.com/owner/repo/issues/1"
            )
        assert "Error" in result["title"]

    @patch("src.tools.github_tools.Github")
    def test_fetch_success(self, MockGithub):
        mock_client = MockGithub.return_value
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_issue.title = "Bug: something broke"
        mock_issue.body = "Steps to reproduce..."
        mock_repo.get_issue.return_value = mock_issue
        mock_client.get_repo.return_value = mock_repo

        tool = GitHubTool(token="fake")
        result = tool.fetch_issue_details(
            "https://github.com/owner/repo/issues/1"
        )

        assert result["title"] == "Bug: something broke"
        assert result["body"] == "Steps to reproduce..."

    @patch("src.tools.github_tools.Github")
    def test_fetch_malformed_url(self, MockGithub):
        tool = GitHubTool(token="fake")
        with pytest.raises(ValueError):
            tool.fetch_issue_details("not-a-url")


class TestGitHubToolClone:
    """Tests for GitHubTool.clone_repository()."""

    def test_clone_existing_repo_resets(self, tmp_repo):
        """When .git exists, clone resets instead of cloning."""
        tool = GitHubTool(token="fake")
        # tmp_repo already has .git
        result = tool.clone_repository(
            "https://github.com/owner/repo/issues/1",
            tmp_repo,
        )
        assert result is True
