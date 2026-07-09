import os
import subprocess
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.docker_sandbox import DockerSandbox
from src.logging_config import get_logger
from src.metrics import RunMetrics

logger = get_logger(__name__)


def _preflight_syntax_check(file_path: str) -> str | None:
    """
    Run `python -m py_compile` on a file to catch syntax errors instantly.
    Returns None if syntax is valid, or the error message if invalid.
    """
    try:
        result = subprocess.run(
            ["python", "-m", "py_compile", file_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return (result.stderr or result.stdout).strip()
        return None
    except subprocess.TimeoutExpired:
        return f"Pre-flight syntax check timed out for {file_path}"
    except Exception as e:
        return f"Pre-flight check error: {str(e)}"


def tester_node(state: ASEState, metrics: RunMetrics | None = None):
    """
    SRS Tester: Verify the Coder's fix.
    1. Pre-flight: fast syntax check on modified files & test script (no Docker needed).
    2. If syntax is clean, run the full test in the Docker Sandbox.
    3. If tests fail, explain why to the Coder.
    """
    node_metric = metrics.start_node("tester") if metrics else None
    logger.info(
        "Tester node started (attempt %d)",
        state.get("validation_attempts", 0) + 1,
        extra={
            "node": "tester",
            "attempt": state.get("validation_attempts", 0) + 1,
        },
    )

    test_script_content = state.get("test_script", "")
    if not test_script_content:
        logger.warning(
            "No test script provided by Coder", extra={"node": "tester"}
        )
        if node_metric and metrics:
            metrics.record_error(node_metric, "No test script provided")
            metrics.end_node(node_metric, success=False)
        return {
            "test_logs": "No test script provided by Coder.",
            "test_passed": False,
            "test_explanation": "Coder failed to generate a test script.",
            "validation_attempts": state.get("validation_attempts", 0) + 1,
        }

    # --- PRE-FLIGHT: Syntax Check (instant, no Docker) ---
    syntax_errors = []

    # Check modified source files
    for file_path, code_content in state.get("updated_code", {}).items():
        if not file_path.endswith(".py"):
            continue

        # Strip leading repo basename if present
        repo_basename = os.path.basename(
            state["repo_path"].rstrip(os.sep)
        )
        clean_path = file_path
        if file_path.startswith(f"{repo_basename}/"):
            clean_path = file_path[len(repo_basename) + 1 :]
        elif file_path.startswith(f"./{repo_basename}/"):
            clean_path = file_path[len(repo_basename) + 3 :]

        full_path = os.path.join(state["repo_path"], clean_path)
        if os.path.exists(full_path):
            err = _preflight_syntax_check(full_path)
            if err:
                syntax_errors.append(
                    f"Syntax error in {file_path}:\n{err}"
                )

    # Check the test script itself
    tmp_test_path = None
    try:
        tmp_dir = os.path.join(state["repo_path"], ".preflight_tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_test_path = os.path.join(tmp_dir, "test_fix.py")
        with open(tmp_test_path, "w", encoding="utf-8") as f:
            f.write(test_script_content)

        err = _preflight_syntax_check(tmp_test_path)
        if err:
            syntax_errors.append(f"Syntax error in test script:\n{err}")
    finally:
        # Cleanup
        try:
            if tmp_test_path and os.path.exists(tmp_test_path):
                os.remove(tmp_test_path)
            if tmp_dir and os.path.exists(tmp_dir):
                os.rmdir(tmp_dir)
        except Exception:
            pass

    if syntax_errors:
        combined = "\n\n".join(syntax_errors)
        logger.warning(
            "Pre-flight syntax check failed, skipping Docker",
            extra={"node": "tester"},
        )
        if node_metric and metrics:
            metrics.record_error(node_metric, "Syntax errors detected")
            metrics.end_node(node_metric, success=False)
        return {
            "test_logs": f"PRE-FLIGHT SYNTAX CHECK FAILED:\n{combined}",
            "test_passed": False,
            "test_explanation": (
                "Your code has syntax errors that must be fixed "
                f"before testing:\n{combined}"
            ),
            "validation_attempts": state.get("validation_attempts", 0) + 1,
        }

    logger.info(
        "Pre-flight syntax check passed, launching Docker Sandbox",
        extra={"node": "tester"},
    )

    # --- FULL TEST: Docker Sandbox ---
    try:
        sandbox = DockerSandbox()
    except Exception as e:
        error_msg = f"Docker is not available: {str(e)}"
        logger.error(error_msg, extra={"node": "tester"})
        if node_metric and metrics:
            metrics.record_error(node_metric, error_msg)
            metrics.end_node(node_metric, success=False)
        return {
            "test_logs": error_msg,
            "test_passed": False,
            "test_explanation": (
                "Docker sandbox could not be initialized. "
                "Ensure Docker Desktop is running."
            ),
            "validation_attempts": state.get("validation_attempts", 0) + 1,
        }

    result = sandbox.run_test(state["repo_path"], test_script_content)

    passed = result["exit_code"] == 0
    logs = result["logs"]

    explanation = ""
    if not passed:
        # Explain why it failed to the coder
        try:
            llm = ChatGroq(
                model_name="llama-3.3-70b-versatile",
                api_key=state.get("groq_api_key"),
            )
            explain_prompt = f"""
        Test Script:
        {test_script_content}
        
        Test Logs:
        {logs}
        
        The test failed. Explain why it failed so the Coder can fix it.
        Be concise.
        """
            explanation_resp = llm.invoke(explain_prompt)
            explanation = explanation_resp.content.strip()

            # Track LLM token usage
            if node_metric and hasattr(
                explanation_resp, "response_metadata"
            ):
                token_usage = (
                    explanation_resp.response_metadata.get(
                        "token_usage", {}
                    )
                )
                if metrics and token_usage:
                    metrics.record_llm_tokens(
                        node_metric,
                        prompt_tokens=token_usage.get(
                            "prompt_tokens", 0
                        ),
                        completion_tokens=token_usage.get(
                            "completion_tokens", 0
                        ),
                    )
        except Exception as e:
            logger.warning(
                "LLM explanation call failed, using raw logs: %s",
                str(e),
                extra={"node": "tester"},
            )
            explanation = f"Test failed. Raw logs:\n{logs}"

    logger.info(
        "Tests %s", "passed" if passed else "failed",
        extra={"node": "tester"},
    )

    if node_metric and metrics:
        if not passed:
            metrics.record_error(node_metric, "Tests failed")
        metrics.end_node(node_metric, success=passed)

    return {
        "test_logs": logs,
        "test_passed": passed,
        "test_explanation": explanation,  # Feedback for Coder
        "validation_attempts": state.get("validation_attempts", 0) + 1,
    }
