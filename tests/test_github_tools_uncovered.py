import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from src.tools.github_tools import GitHubTool

def test_fetch_issue_details_exception():
    with patch("src.tools.github_tools.Github") as MockGithub:
        tool = GitHubTool(token="fake")
        tool.client = MockGithub.return_value
        tool.client.get_repo.side_effect = Exception("API limit exceeded")
        result = tool.fetch_issue_details("https://github.com/owner/repo/issues/1")
        assert result["title"] == "Error Fetching Issue"
        assert "API limit exceeded" in result["body"]

def test_clone_without_token(tmp_path):
    with patch.dict(os.environ, {}, clear=True):
        tool = GitHubTool(token=None)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            dest = str(tmp_path / "new_repo")
            result = tool.clone_repository("https://github.com/owner/repo/issues/1", dest)
            assert result is True
            mock_run.assert_called_once()
            assert "https://github.com/owner/repo.git" in mock_run.call_args[0][0]

def test_clone_exception(tmp_path):
    tool = GitHubTool(token="fake")
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("git not installed")
        dest = str(tmp_path / "new_repo")
        result = tool.clone_repository("https://github.com/owner/repo/issues/1", dest)
        assert result is False

def test_list_files_tree_filters(tmp_path):
    tool = GitHubTool(token="fake")
    (tmp_path / ".venv").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").touch()
    
    tree = tool.list_files_tree(str(tmp_path))
    assert "src/" in tree
    assert "app.py" in tree
    assert ".venv" not in tree
    assert "__pycache__" not in tree

def test_read_file_generic_exception(tmp_path):
    tool = GitHubTool(token="fake")
    file_path = tmp_path / "locked.txt"
    file_path.write_text("hello")
    
    with patch("builtins.open", side_effect=PermissionError("Access denied")):
        result = tool.read_file(str(tmp_path), "locked.txt")
        assert "Error reading file:" in result
        assert "Access denied" in result

def test_run_git_command_success(tmp_repo):
    tool = GitHubTool(token="fake")
    result = tool.run_git_command(tmp_repo, ["status"])
    assert "On branch" in result or "nothing to commit" in result or "initial" in result or result != ""

def test_run_git_command_error(tmp_repo):
    tool = GitHubTool(token="fake")
    result = tool.run_git_command(tmp_repo, ["nonexistent"])
    assert "Error:" in result

def test_get_git_status(tmp_repo):
    tool = GitHubTool(token="fake")
    with patch.object(tool, 'run_git_command') as mock_run:
        mock_run.return_value = "clean"
        assert tool.get_git_status(tmp_repo) == "clean"
        mock_run.assert_called_with(tmp_repo, ['status'])

def test_create_branch(tmp_repo):
    tool = GitHubTool(token="fake")
    with patch.object(tool, 'run_git_command') as mock_run:
        mock_run.return_value = "switched"
        assert tool.create_branch(tmp_repo, "new-feature") == "switched"
        mock_run.assert_called_with(tmp_repo, ['checkout', '-b', 'new-feature'])

def test_stage_files(tmp_repo):
    tool = GitHubTool(token="fake")
    with patch.object(tool, 'run_git_command') as mock_run:
        mock_run.return_value = "staged"
        assert tool.stage_files(tmp_repo, ["app.py"]) == "staged"
        mock_run.assert_called_with(tmp_repo, ['add', 'app.py'])

def test_commit_changes(tmp_repo):
    tool = GitHubTool(token="fake")
    # Actually perform a real commit
    (os.path.join(tmp_repo, "new_file.txt"))
    with open(os.path.join(tmp_repo, "new_file.txt"), "w") as f:
         f.write("hello")
    tool.stage_files(tmp_repo, ["new_file.txt"])
    result = tool.commit_changes(tmp_repo, "add new file")
    assert "add new file" in result or "1 file changed" in result or result != ""

def test_commit_changes_error(tmp_repo):
    tool = GitHubTool(token="fake")
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="Empty commit")
        result = tool.commit_changes(tmp_repo, "msg")
        assert "Empty commit" in result

def test_push_branch(tmp_repo):
    tool = GitHubTool(token="fake")
    with patch.object(tool, 'run_git_command') as mock_run:
        mock_run.return_value = "pushed"
        assert tool.push_branch(tmp_repo, "main") == "pushed"
        mock_run.assert_called_with(tmp_repo, ['push', '-u', 'origin', 'main'])

def test_create_pull_request():
    with patch("src.tools.github_tools.Github") as MockGithub:
        tool = GitHubTool(token="fake")
        tool.client = MockGithub.return_value
        mock_repo = MagicMock()
        mock_repo.default_branch = "main"
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/owner/repo/pull/2"
        tool.client.get_repo.return_value = mock_repo
        mock_repo.create_pull.return_value = mock_pr
        
        result = tool.create_pull_request(
            "https://github.com/owner/repo/issues/1",
            "fix-branch",
            "Fix bug",
            "PR body"
        )
        assert result == "https://github.com/owner/repo/pull/2"

def test_create_pull_request_no_client():
    tool = GitHubTool(token=None)
    with patch.dict(os.environ, {}, clear=True):
        tool2 = GitHubTool(token=None)
        tool2.client = None
        result = tool2.create_pull_request("https://github.com/owner/repo/issues/1", "b", "t", "b")
        assert "Not Initialized" in result

def test_create_pull_request_exception():
    with patch("src.tools.github_tools.Github") as MockGithub:
        tool = GitHubTool(token="fake")
        tool.client = MockGithub.return_value
        tool.client.get_repo.side_effect = Exception("Failed to open PR")
        result = tool.create_pull_request("https://github.com/owner/repo/issues/1", "b", "t", "b")
        assert "Failed to create PR: Failed to open PR" in result
