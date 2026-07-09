"""
Unit tests for the Researcher agent node.
"""

from unittest.mock import patch, MagicMock

from src.agents.researcher import researcher_node


class TestResearcherNode:
    """Tests for researcher_node()."""

    @patch("src.agents.researcher.ChatGroq")
    def test_parses_file_from_llm_response(
        self, MockChatGroq, mock_state, mock_llm_response, run_metrics
    ):
        """Researcher correctly extracts FILE: marker from LLM output."""
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.return_value = mock_llm_response(
            "FILE: src/app.py\nSNIPPET:\ndef add(a, b):\n    return a - b"
        )

        result = researcher_node(mock_state, metrics=run_metrics)

        assert result["files_to_modify"] == ["src/app.py"]
        assert "src/app.py" in result["research_summary"]

    @patch("src.agents.researcher.ChatGroq")
    def test_handles_no_file_marker(
        self, MockChatGroq, mock_state, mock_llm_response, run_metrics
    ):
        """When LLM returns no FILE: marker, files_to_modify is empty."""
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.return_value = mock_llm_response(
            "I couldn't find a specific file causing this issue."
        )

        result = researcher_node(mock_state, metrics=run_metrics)

        assert result["files_to_modify"] == []
        assert result["research_summary"] != ""

    @patch("src.agents.researcher.ChatGroq")
    def test_handles_llm_exception(
        self, MockChatGroq, mock_state, run_metrics
    ):
        """Researcher gracefully handles LLM API errors."""
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.side_effect = Exception("Rate limit exceeded")

        result = researcher_node(mock_state, metrics=run_metrics)

        assert result["files_to_modify"] == []
        assert "error" in result["research_summary"].lower()

    @patch("src.agents.researcher.ChatGroq")
    def test_handles_file_with_snippet_on_same_line(
        self, MockChatGroq, mock_state, mock_llm_response, run_metrics
    ):
        """Handles edge case where SNIPPET: is on the same line as FILE:."""
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.return_value = mock_llm_response(
            "FILE: utils/helper.py SNIPPET:\ndef broken():\n    pass"
        )

        result = researcher_node(mock_state, metrics=run_metrics)

        assert result["files_to_modify"] == ["utils/helper.py"]

    @patch("src.agents.researcher.ChatGroq")
    def test_tracks_llm_tokens(
        self, MockChatGroq, mock_state, mock_llm_response, run_metrics
    ):
        """Researcher records LLM token usage in metrics."""
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.return_value = mock_llm_response(
            "FILE: src/app.py\nSNIPPET:\ncode",
            prompt_tokens=100,
            completion_tokens=50,
        )

        researcher_node(mock_state, metrics=run_metrics)

        summary = run_metrics.to_dict()
        assert summary["total_prompt_tokens"] == 100
        assert summary["total_completion_tokens"] == 50

    @patch("src.agents.researcher.ChatGroq")
    def test_works_without_metrics(
        self, MockChatGroq, mock_state, mock_llm_response
    ):
        """Researcher works when metrics=None (backwards compatible)."""
        mock_llm = MockChatGroq.return_value
        mock_llm.invoke.return_value = mock_llm_response(
            "FILE: src/app.py\nSNIPPET:\ncode"
        )

        result = researcher_node(mock_state, metrics=None)

        assert result["files_to_modify"] == ["src/app.py"]
