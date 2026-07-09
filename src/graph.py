from langgraph.graph import StateGraph, START, END
from src.state import ASEState
from src.agents.researcher import researcher_node
from src.agents.coder import coder_node
from src.agents.tester import tester_node
from src.logging_config import get_logger
from src.metrics import RunMetrics

logger = get_logger(__name__)


def should_continue(state: ASEState) -> str:
    """ Loop back to coder if tests fail, up to 3 times. """
    if state.get("test_passed", False):
        return "end"

    if state.get("validation_attempts", 0) >= 3:
        logger.warning(
            "Max validation attempts (%d) reached, exiting loop",
            state.get("validation_attempts", 0),
        )
        return "end"

    return "coder"


def create_ase_graph(metrics: RunMetrics | None = None):
    """
    Build the 3-Agent Loop: Researcher -> Coder -> Tester -> (Coder if fail).

    Args:
        metrics: Optional per-run metrics collector. When provided,
                 each node wrapper closes over this instance so metrics
                 are scoped to a single orchestration call — no singletons,
                 no cross-session leakage.
    """

    # Wrap raw node functions to inject the metrics instance via closure
    def _researcher(state: ASEState):
        return researcher_node(state, metrics=metrics)

    def _coder(state: ASEState):
        return coder_node(state, metrics=metrics)

    def _tester(state: ASEState):
        result = tester_node(state, metrics=metrics)
        # Track validation attempts in metrics
        if metrics is not None:
            metrics.total_validation_attempts = result.get(
                "validation_attempts", 0
            )
        return result

    workflow = StateGraph(ASEState)

    workflow.add_node("researcher", _researcher)
    workflow.add_node("coder", _coder)
    workflow.add_node("tester", _tester)

    workflow.add_edge(START, "researcher")
    workflow.add_edge("researcher", "coder")
    workflow.add_edge("coder", "tester")

    workflow.add_conditional_edges(
        "tester",
        should_continue,
        {
            "coder": "coder",
            "end": END
        }
    )

    return workflow.compile()
