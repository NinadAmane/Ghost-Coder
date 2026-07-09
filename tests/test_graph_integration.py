"""
Integration tests for the LangGraph state machine.

These tests drive the REAL LangGraph graph through actual state transitions,
including the should_continue() routing logic. LLM and Docker calls are mocked
but the graph topology, node sequencing, and retry loop are exercised for real.
"""

from unittest.mock import patch, MagicMock

import pytest

from src.graph import create_ase_graph, should_continue
from src.metrics import RunMetrics


# ============================================================
# Unit tests for the routing function
# ============================================================


class TestShouldContinue:
    """Tests for should_continue() routing decisions."""

    def test_returns_end_on_success(self):
        state = {"test_passed": True, "validation_attempts": 1}
        assert should_continue(state) == "end"

    def test_returns_coder_on_failure(self):
        state = {"test_passed": False, "validation_attempts": 1}
        assert should_continue(state) == "coder"

    def test_returns_end_at_max_attempts(self):
        state = {"test_passed": False, "validation_attempts": 3}
        assert should_continue(state) == "end"

    def test_returns_coder_just_below_max(self):
        state = {"test_passed": False, "validation_attempts": 2}
        assert should_continue(state) == "coder"

    def test_handles_missing_keys(self):
        # Defaults: test_passed=False, validation_attempts=0
        assert should_continue({}) == "coder"


# ============================================================
# Integration tests — real LangGraph graph, mocked LLM/Docker
# ============================================================


def _make_mock_llm_response(content, prompt_tokens=10, completion_tokens=20):
    """Helper to create a mock LLM response."""
    resp = MagicMock()
    resp.content = content
    resp.response_metadata = {
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
    }
    return resp


class TestGraphIntegrationSuccessPath:
    """
    Integration test: Researcher -> Coder -> Tester with all 3 succeeding
    on the first attempt. Exercises the real LangGraph state machine.
    """

    @patch("src.agents.tester.DockerSandbox")
    @patch("src.agents.tester.ChatGroq")
    @patch("src.agents.coder.ChatGroq")
    @patch("src.agents.researcher.ChatGroq")
    def test_success_path(
        self,
        MockResearcherLLM,
        MockCoderLLM,
        MockTesterLLM,
        MockDockerSandbox,
        tmp_repo,
    ):
        """Full success path: researcher finds file, coder patches, tester passes."""
        # --- Researcher mock ---
        researcher_llm = MockResearcherLLM.return_value
        researcher_llm.invoke.return_value = _make_mock_llm_response(
            "FILE: src/app.py\nSNIPPET:\ndef add(a, b):\n    return a - b"
        )

        # --- Coder mock (2 calls: fix + test script) ---
        coder_llm = MockCoderLLM.return_value
        coder_llm.invoke.side_effect = [
            _make_mock_llm_response(
                "<<<<<<< SEARCH\n"
                "    return a - b  # BUG: should be a + b\n"
                "=======\n"
                "    return a + b\n"
                ">>>>>>> REPLACE"
            ),
            _make_mock_llm_response("assert True  # test passes"),
        ]

        # --- Tester mock (Docker succeeds) ---
        mock_sandbox = MockDockerSandbox.return_value
        mock_sandbox.run_test.return_value = {
            "exit_code": 0,
            "logs": "All tests passed!",
        }

        # --- Run the REAL graph ---
        metrics = RunMetrics()
        metrics.start_run()
        graph = create_ase_graph(metrics=metrics)

        initial_state = {
            "issue_url": "https://github.com/owner/repo/issues/1",
            "issue_description": "add() subtracts instead of adding",
            "repo_path": tmp_repo,
            "github_token": "fake-token",
            "groq_api_key": "fake-key",
            "files_to_modify": [],
            "research_summary": "",
            "updated_code": {},
            "test_script": "",
            "test_logs": "",
            "test_passed": False,
            "test_explanation": "",
            "validation_attempts": 0,
        }

        final_state = initial_state.copy()
        nodes_visited = []
        for output in graph.stream(initial_state):
            for node_name, state_update in output.items():
                nodes_visited.append(node_name)
                final_state.update(state_update)

        metrics.end_run(success=final_state["test_passed"])

        # Assertions
        assert final_state["test_passed"] is True
        assert final_state["validation_attempts"] == 1
        assert nodes_visited == ["researcher", "coder", "tester"]


class TestGraphIntegrationRetryThenSuccess:
    """
    Integration test: First tester run fails, graph routes back to coder,
    second attempt succeeds. Verifies the REAL retry transition in LangGraph.
    """

    @patch("src.agents.tester.DockerSandbox")
    @patch("src.agents.tester.ChatGroq")
    @patch("src.agents.coder.ChatGroq")
    @patch("src.agents.researcher.ChatGroq")
    def test_retry_then_success(
        self,
        MockResearcherLLM,
        MockCoderLLM,
        MockTesterLLM,
        MockDockerSandbox,
        tmp_repo,
    ):
        """Fail once, retry, succeed on second attempt."""
        # --- Researcher mock ---
        researcher_llm = MockResearcherLLM.return_value
        researcher_llm.invoke.return_value = _make_mock_llm_response(
            "FILE: src/app.py\nSNIPPET:\ndef add(a, b):\n    return a - b"
        )

        # --- Coder mock ---
        # Call sequence: fix1, test1, fix2, test2
        coder_llm = MockCoderLLM.return_value
        coder_llm.invoke.side_effect = [
            # First attempt: generates a bad fix (still subtracts)
            _make_mock_llm_response("def add(a, b):\n    return a - b\n"),
            _make_mock_llm_response("assert add(1, 2) == 3"),
            # Second attempt: generates the correct fix
            _make_mock_llm_response(
                "<<<<<<< SEARCH\n"
                "    return a - b  # BUG: should be a + b\n"
                "=======\n"
                "    return a + b\n"
                ">>>>>>> REPLACE"
            ),
            _make_mock_llm_response("assert add(1, 2) == 3"),
        ]

        # --- Tester mock ---
        # First call: Docker fails. Second call: Docker succeeds.
        tester_llm = MockTesterLLM.return_value
        tester_llm.invoke.return_value = _make_mock_llm_response(
            "The test failed because add still subtracts."
        )

        mock_sandbox = MockDockerSandbox.return_value
        mock_sandbox.run_test.side_effect = [
            {"exit_code": 1, "logs": "AssertionError: -1 != 3"},
            {"exit_code": 0, "logs": "All tests passed!"},
        ]

        # --- Run the REAL graph ---
        metrics = RunMetrics()
        metrics.start_run()
        graph = create_ase_graph(metrics=metrics)

        initial_state = {
            "issue_url": "https://github.com/owner/repo/issues/1",
            "issue_description": "add() subtracts instead of adding",
            "repo_path": tmp_repo,
            "github_token": "fake-token",
            "groq_api_key": "fake-key",
            "files_to_modify": [],
            "research_summary": "",
            "updated_code": {},
            "test_script": "",
            "test_logs": "",
            "test_passed": False,
            "test_explanation": "",
            "validation_attempts": 0,
        }

        final_state = initial_state.copy()
        nodes_visited = []
        for output in graph.stream(initial_state):
            for node_name, state_update in output.items():
                nodes_visited.append(node_name)
                final_state.update(state_update)

        metrics.end_run(success=final_state["test_passed"])

        # Assertions: should have gone researcher -> coder -> tester -> coder -> tester
        assert final_state["test_passed"] is True
        assert final_state["validation_attempts"] == 2
        assert nodes_visited == [
            "researcher", "coder", "tester", "coder", "tester"
        ]


class TestGraphIntegrationMaxRetriesExhausted:
    """
    Integration test: All 3 tester attempts fail. Verifies the graph
    exits after max retries via the REAL should_continue() routing.
    """

    @patch("src.agents.tester.DockerSandbox")
    @patch("src.agents.tester.ChatGroq")
    @patch("src.agents.coder.ChatGroq")
    @patch("src.agents.researcher.ChatGroq")
    def test_max_retries_exhausted(
        self,
        MockResearcherLLM,
        MockCoderLLM,
        MockTesterLLM,
        MockDockerSandbox,
        tmp_repo,
    ):
        """Fail 3 times, graph exits via max-retry routing."""
        # --- Researcher mock ---
        researcher_llm = MockResearcherLLM.return_value
        researcher_llm.invoke.return_value = _make_mock_llm_response(
            "FILE: src/app.py\nSNIPPET:\ndef add(a, b):\n    return a - b"
        )

        # --- Coder mock: always returns a bad fix (full rewrite fallback) ---
        coder_llm = MockCoderLLM.return_value
        coder_llm.invoke.return_value = _make_mock_llm_response(
            "def add(a, b):\n    return a - b  # still wrong\n"
        )

        # --- Tester mock: always fails ---
        tester_llm = MockTesterLLM.return_value
        tester_llm.invoke.return_value = _make_mock_llm_response(
            "The function still subtracts."
        )

        mock_sandbox = MockDockerSandbox.return_value
        mock_sandbox.run_test.return_value = {
            "exit_code": 1,
            "logs": "AssertionError: -1 != 3",
        }

        # --- Run the REAL graph ---
        metrics = RunMetrics()
        metrics.start_run()
        graph = create_ase_graph(metrics=metrics)

        initial_state = {
            "issue_url": "https://github.com/owner/repo/issues/1",
            "issue_description": "add() subtracts instead of adding",
            "repo_path": tmp_repo,
            "github_token": "fake-token",
            "groq_api_key": "fake-key",
            "files_to_modify": [],
            "research_summary": "",
            "updated_code": {},
            "test_script": "",
            "test_logs": "",
            "test_passed": False,
            "test_explanation": "",
            "validation_attempts": 0,
        }

        final_state = initial_state.copy()
        nodes_visited = []
        for output in graph.stream(initial_state):
            for node_name, state_update in output.items():
                nodes_visited.append(node_name)
                final_state.update(state_update)

        metrics.end_run(success=final_state["test_passed"])

        # Assertions:
        # researcher -> coder -> tester -> coder -> tester -> coder -> tester
        # (3 tester attempts, should_continue returns "end" at attempt 3)
        assert final_state["test_passed"] is False
        assert final_state["validation_attempts"] == 3
        assert nodes_visited == [
            "researcher",
            "coder", "tester",
            "coder", "tester",
            "coder", "tester",
        ]
        assert nodes_visited.count("tester") == 3
        assert nodes_visited.count("coder") == 3
