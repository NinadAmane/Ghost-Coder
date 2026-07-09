"""
Unit tests for the Coder agent node and its parsing utilities.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.agents.coder import (
    _strip_markdown_fences,
    _parse_search_replace_blocks,
    _apply_search_replace,
    coder_node,
)


# ============================================================
# Unit tests for parsing utilities
# ============================================================


class TestStripMarkdownFences:
    """Tests for _strip_markdown_fences()."""

    def test_removes_python_fence(self):
        text = '```python\ndef hello():\n    pass\n```'
        assert _strip_markdown_fences(text) == "def hello():\n    pass"

    def test_removes_bare_fence(self):
        text = '```\nfoo\n```'
        assert _strip_markdown_fences(text) == "foo"

    def test_no_fences_unchanged(self):
        text = "def hello():\n    pass"
        assert _strip_markdown_fences(text) == text

    def test_empty_string(self):
        assert _strip_markdown_fences("") == ""

    def test_only_fences(self):
        text = "```python\n```"
        assert _strip_markdown_fences(text) == ""


class TestParseSearchReplaceBlocks:
    """Tests for _parse_search_replace_blocks()."""

    def test_single_block(self):
        text = (
            "<<<<<<< SEARCH\n"
            "old code\n"
            "=======\n"
            "new code\n"
            ">>>>>>> REPLACE"
        )
        blocks = _parse_search_replace_blocks(text)
        assert len(blocks) == 1
        assert blocks[0]["search"] == "old code"
        assert blocks[0]["replace"] == "new code"

    def test_multiple_blocks(self):
        text = (
            "<<<<<<< SEARCH\n"
            "old1\n"
            "=======\n"
            "new1\n"
            ">>>>>>> REPLACE\n"
            "\n"
            "<<<<<<< SEARCH\n"
            "old2\n"
            "=======\n"
            "new2\n"
            ">>>>>>> REPLACE"
        )
        blocks = _parse_search_replace_blocks(text)
        assert len(blocks) == 2
        assert blocks[0]["search"] == "old1"
        assert blocks[1]["replace"] == "new2"

    def test_multiline_blocks(self):
        text = (
            "<<<<<<< SEARCH\n"
            "line1\nline2\nline3\n"
            "=======\n"
            "new1\nnew2\n"
            ">>>>>>> REPLACE"
        )
        blocks = _parse_search_replace_blocks(text)
        assert len(blocks) == 1
        assert "line2" in blocks[0]["search"]

    def test_no_blocks_returns_empty(self):
        assert _parse_search_replace_blocks("just some code") == []

    def test_malformed_block_missing_separator(self):
        text = "<<<<<<< SEARCH\nold code\n>>>>>>> REPLACE"
        assert _parse_search_replace_blocks(text) == []


class TestApplySearchReplace:
    """Tests for _apply_search_replace()."""

    def test_exact_match(self):
        original = "def add(a, b):\n    return a - b\n"
        blocks = [{"search": "return a - b", "replace": "return a + b"}]
        result = _apply_search_replace(original, blocks)
        assert "return a + b" in result
        assert "return a - b" not in result

    def test_whitespace_tolerant_match(self):
        original = "def add(a, b):   \n    return a - b   \n"
        blocks = [{"search": "def add(a, b):\n    return a - b", "replace": "def add(a, b):\n    return a + b"}]
        result = _apply_search_replace(original, blocks)
        assert "return a + b" in result

    def test_no_match_skips_block(self):
        original = "def add(a, b):\n    return a + b\n"
        blocks = [{"search": "completely different code", "replace": "replacement"}]
        result = _apply_search_replace(original, blocks)
        assert result == original

    def test_multiple_blocks_applied(self):
        original = "import os\nimport sys\ndef foo():\n    pass\n"
        blocks = [
            {"search": "import sys", "replace": "import json"},
            {"search": "pass", "replace": "return 42"},
        ]
        result = _apply_search_replace(original, blocks)
        assert "import json" in result
        assert "return 42" in result
        assert "import sys" not in result


# ============================================================
# Unit tests for coder_node()
# ============================================================


class TestCoderNode:
    """Tests for coder_node()."""

    @patch("src.agents.coder.ChatGroq")
    def test_applies_search_replace_blocks(
        self, MockChatGroq, mock_state, mock_llm_response, run_metrics, tmp_repo
    ):
        """Coder applies SEARCH/REPLACE blocks and writes the file."""
        mock_state["files_to_modify"] = ["src/app.py"]
        mock_state["research_summary"] = "Bug in add function"

        fix_response = mock_llm_response(
            "<<<<<<< SEARCH\n"
            "    return a - b  # BUG: should be a + b\n"
            "=======\n"
            "    return a + b\n"
            ">>>>>>> REPLACE"
        )
        test_response = mock_llm_response("assert add(1, 2) == 3")

        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = [fix_response, test_response]

        result = coder_node(mock_state, metrics=run_metrics)

        assert "src/app.py" in result["updated_code"]
        assert "return a + b" in result["updated_code"]["src/app.py"]
        assert result["test_script"] == "assert add(1, 2) == 3"

    @patch("src.agents.coder.ChatGroq")
    def test_falls_back_to_full_rewrite(
        self, MockChatGroq, mock_state, mock_llm_response, run_metrics
    ):
        """When LLM returns no blocks, coder uses raw output as file content."""
        mock_state["files_to_modify"] = ["src/app.py"]
        mock_state["research_summary"] = "Bug in add function"

        # LLM returns full code instead of blocks
        fix_response = mock_llm_response(
            "def add(a, b):\n    return a + b\n"
        )
        test_response = mock_llm_response("assert True")

        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = [fix_response, test_response]

        result = coder_node(mock_state, metrics=run_metrics)

        assert "src/app.py" in result["updated_code"]
        assert "return a + b" in result["updated_code"]["src/app.py"]

    def test_handles_empty_files_to_modify(
        self, mock_state, run_metrics
    ):
        """When no files to modify, coder returns early with empty results."""
        mock_state["files_to_modify"] = []

        result = coder_node(mock_state, metrics=run_metrics)

        assert result["updated_code"] == {}
        assert result["test_script"] == ""

    @patch("src.agents.coder.ChatGroq")
    def test_handles_file_not_found(
        self, MockChatGroq, mock_state, mock_llm_response, run_metrics
    ):
        """Coder skips files that don't exist in the repo."""
        mock_state["files_to_modify"] = ["nonexistent/file.py"]
        mock_state["research_summary"] = "Some research"

        test_response = mock_llm_response("assert True")
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = [test_response]

        result = coder_node(mock_state, metrics=run_metrics)

        # File not found should be skipped, only test script generated
        assert "nonexistent/file.py" not in result["updated_code"]

    @patch("src.agents.coder.ChatGroq")
    def test_blocks_directory_traversal(
        self, MockChatGroq, mock_state, mock_llm_response, run_metrics
    ):
        """Coder rejects file paths that escape the repo directory."""
        mock_state["files_to_modify"] = ["../../etc/passwd"]
        mock_state["research_summary"] = "Malicious attempt"

        fix_response = mock_llm_response("malicious content")
        test_response = mock_llm_response("assert True")
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = [fix_response, test_response]

        result = coder_node(mock_state, metrics=run_metrics)

        # Traversal should be blocked
        assert "../../etc/passwd" not in result["updated_code"]

    @patch("src.agents.coder.ChatGroq")
    def test_handles_llm_exception(
        self, MockChatGroq, mock_state, run_metrics
    ):
        """Coder gracefully handles LLM API errors."""
        mock_state["files_to_modify"] = ["src/app.py"]
        mock_state["research_summary"] = "Some research"

        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = Exception("API timeout")

        result = coder_node(mock_state, metrics=run_metrics)

        assert result["test_script"] == ""

    @patch("src.agents.coder.ChatGroq")
    def test_includes_failure_context_on_retry(
        self, MockChatGroq, mock_state, mock_llm_response, run_metrics
    ):
        """On retry, coder includes previous test failure feedback in prompt."""
        mock_state["files_to_modify"] = ["src/app.py"]
        mock_state["research_summary"] = "Bug in add function"
        mock_state["test_explanation"] = "AssertionError: expected 3, got -1"

        fix_response = mock_llm_response(
            "<<<<<<< SEARCH\n"
            "    return a - b  # BUG: should be a + b\n"
            "=======\n"
            "    return a + b\n"
            ">>>>>>> REPLACE"
        )
        test_response = mock_llm_response("assert add(1, 2) == 3")

        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = [fix_response, test_response]

        coder_node(mock_state, metrics=run_metrics)

        # Verify failure context was included in the prompt
        call_args = mock_llm.invoke.call_args_list[0]
        prompt_text = call_args[0][0]
        assert "Previous Fix Failed" in prompt_text
        assert "AssertionError" in prompt_text
