"""
Unit tests for RunMetrics and logging_config.
"""

import time
import json
import logging

from src.metrics import RunMetrics, NodeMetric
from src.logging_config import get_logger, JSONFormatter


class TestRunMetrics:
    """Tests for RunMetrics."""

    def test_records_node_latency(self):
        metrics = RunMetrics()
        metrics.start_run()

        node = metrics.start_node("researcher")
        time.sleep(0.01)  # ~10ms
        metrics.end_node(node, success=True)

        summary = metrics.to_dict()
        assert summary["nodes"]["researcher"]["total_duration_ms"] > 0
        assert summary["nodes"]["researcher"]["all_succeeded"] is True

    def test_records_tokens(self):
        metrics = RunMetrics()
        metrics.start_run()

        node = metrics.start_node("coder")
        metrics.record_llm_tokens(node, prompt_tokens=100, completion_tokens=50)
        metrics.record_llm_tokens(node, prompt_tokens=200, completion_tokens=80)
        metrics.end_node(node, success=True)

        summary = metrics.to_dict()
        assert summary["total_prompt_tokens"] == 300
        assert summary["total_completion_tokens"] == 130
        assert summary["total_tokens"] == 430

    def test_records_errors(self):
        metrics = RunMetrics()
        metrics.start_run()

        node = metrics.start_node("tester")
        metrics.record_error(node, "Test failed")
        metrics.record_error(node, "Docker timeout")
        metrics.end_node(node, success=False)

        summary = metrics.to_dict()
        assert summary["nodes"]["tester"]["errors"] == [
            "Test failed",
            "Docker timeout",
        ]
        assert summary["nodes"]["tester"]["all_succeeded"] is False

    def test_to_dict_serializable(self):
        """Verify to_dict() output is JSON-serializable."""
        metrics = RunMetrics()
        metrics.start_run()
        node = metrics.start_node("researcher")
        metrics.record_llm_tokens(node, 10, 20)
        metrics.end_node(node, success=True)
        metrics.end_run(success=True)

        result = metrics.to_dict()
        # Should not raise
        json_str = json.dumps(result)
        assert "researcher" in json_str

    def test_multiple_executions_of_same_node(self):
        """Tracks multiple executions of the same node (retries)."""
        metrics = RunMetrics()
        metrics.start_run()

        for i in range(3):
            node = metrics.start_node("coder")
            metrics.end_node(node, success=(i == 2))

        summary = metrics.to_dict()
        assert summary["nodes"]["coder"]["executions"] == 3
        assert summary["nodes"]["coder"]["all_succeeded"] is False

    def test_run_duration(self):
        metrics = RunMetrics()
        metrics.start_run()
        time.sleep(0.05)  # 50ms — safe for Windows timer resolution
        metrics.end_run(success=True)

        summary = metrics.to_dict()
        assert summary["run_duration_ms"] >= 10.0, (
            f"Expected >=10ms, got {summary['run_duration_ms']}ms"
        )
        assert summary["final_success"] is True

    def test_fresh_instance_has_no_data(self):
        """Fresh RunMetrics has no nodes and no duration."""
        metrics = RunMetrics()
        summary = metrics.to_dict()
        assert summary["nodes"] == {}
        assert summary["total_tokens"] == 0
        assert summary["run_duration_ms"] == 0


class TestJSONFormatter:
    """Tests for the JSON log formatter."""

    def test_formats_as_json(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="ghost_coder.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "ghost_coder.test"

    def test_includes_extra_fields(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.node = "researcher"
        record.duration_ms = 42.5
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["node"] == "researcher"
        assert parsed["duration_ms"] == 42.5


class TestGetLogger:
    """Tests for get_logger()."""

    def test_returns_named_logger(self):
        logger = get_logger("ghost_coder.test_module")
        assert logger.name == "ghost_coder.test_module"
        assert len(logger.handlers) > 0

    def test_idempotent(self):
        """Calling get_logger twice returns same logger without duplication."""
        logger1 = get_logger("ghost_coder.idempotent_test")
        handler_count = len(logger1.handlers)
        logger2 = get_logger("ghost_coder.idempotent_test")
        assert logger1 is logger2
        assert len(logger2.handlers) == handler_count
