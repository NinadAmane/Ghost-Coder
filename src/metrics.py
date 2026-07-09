"""
Per-run metrics collection for Ghost Coder.

RunMetrics is a plain class — NOT a singleton. It is instantiated fresh
per orchestration call and passed to `create_ase_graph(metrics=...)`.
Node wrappers close over the instance, keeping metrics as side-channel
data outside the LangGraph state dict.

This design avoids cross-run and cross-session leakage in Streamlit.
"""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeMetric:
    """Metrics recorded for a single node execution."""

    node_name: str
    started: bool = False
    completed: bool = False
    success: bool = False
    duration_ms: float = 0.0
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    errors: list[str] = field(default_factory=list)


class RunMetrics:
    """
    Accumulates metrics for a single orchestration run.

    Thread-safety is not needed because LangGraph executes nodes
    sequentially in the 3-agent loop used by this project.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, list[NodeMetric]] = {}
        self._run_start: float = 0.0
        self._run_end: float = 0.0
        self.total_validation_attempts: int = 0
        self.final_success: bool = False

    # -- Run lifecycle --

    def start_run(self) -> None:
        self._run_start = time.monotonic()

    def end_run(self, *, success: bool) -> None:
        self._run_end = time.monotonic()
        self.final_success = success

    # -- Node lifecycle --

    def start_node(self, name: str) -> NodeMetric:
        metric = NodeMetric(node_name=name, started=True)
        metric._start_time = time.monotonic()  # type: ignore[attr-defined]
        self._nodes.setdefault(name, []).append(metric)
        return metric

    def end_node(self, metric: NodeMetric, *, success: bool = True) -> None:
        start = getattr(metric, "_start_time", time.monotonic())
        metric.duration_ms = (time.monotonic() - start) * 1000
        metric.completed = True
        metric.success = success

    def record_llm_tokens(
        self, metric: NodeMetric, prompt_tokens: int, completion_tokens: int
    ) -> None:
        metric.llm_prompt_tokens += prompt_tokens
        metric.llm_completion_tokens += completion_tokens

    def record_error(self, metric: NodeMetric, error: str) -> None:
        metric.errors.append(error)

    # -- Aggregation --

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable summary of the run."""
        total_prompt = 0
        total_completion = 0
        node_summaries = {}
        for name, executions in self._nodes.items():
            durations = [e.duration_ms for e in executions if e.completed]
            errors = []
            for e in executions:
                total_prompt += e.llm_prompt_tokens
                total_completion += e.llm_completion_tokens
                errors.extend(e.errors)
            node_summaries[name] = {
                "executions": len(executions),
                "total_duration_ms": round(sum(durations), 1),
                "avg_duration_ms": round(
                    sum(durations) / len(durations), 1
                )
                if durations
                else 0,
                "all_succeeded": all(e.success for e in executions),
                "errors": errors,
            }

        run_duration = (
            (self._run_end - self._run_start) * 1000
            if self._run_end
            else 0
        )

        return {
            "run_duration_ms": round(run_duration, 1),
            "final_success": self.final_success,
            "total_validation_attempts": self.total_validation_attempts,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "nodes": node_summaries,
        }
