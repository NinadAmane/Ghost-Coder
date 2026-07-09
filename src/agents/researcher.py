import os
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.github_tools import GitHubTool
from src.logging_config import get_logger
from src.metrics import RunMetrics

logger = get_logger(__name__)


def researcher_node(state: ASEState, metrics: RunMetrics | None = None):
    """
    SRS Researcher: Find the specific file and lines causing the issue.
    Output the filename and a code snippet of the problem area.
    """
    node_metric = metrics.start_node("researcher") if metrics else None
    logger.info("Researcher node started", extra={"node": "researcher"})

    try:
        llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            api_key=state.get("groq_api_key"),
        )
        gh_tool = GitHubTool(token=state.get("github_token"))

        # 1. Get repo context (file tree)
        tree = gh_tool.list_files_tree(state["repo_path"])

        # 2. Ask LLM to pick files and explain why
        prompt = f"""
    Issue: {state['issue_description']}
    
    Repository Tree:
    {tree}
    
    Find the specific file and lines causing this issue. 
    Output the filename and a code snippet of the problem area.
    
    IMPORTANT: If the issue involves missing dependencies or third-party libraries (e.g., pandas, sklearn, numpy), 
    you MUST also include 'requirements.txt' in your FILE list, even if it does not exist in the tree.
    
    Format your response as:
    FILE: <path/to/file>
    SNIPPET:
    <code>
    """

        response = llm.invoke(prompt)
        content = response.content

        # Track LLM token usage
        if node_metric and hasattr(response, "response_metadata"):
            token_usage = response.response_metadata.get("token_usage", {})
            if metrics and token_usage:
                metrics.record_llm_tokens(
                    node_metric,
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                )

        # Robust parsing logic
        file_path = ""
        if "FILE:" in content:
            # Extract everything after FILE: until the next newline or keyword
            file_part = content.split("FILE:")[1].split("\n")[0].strip()
            # Remove any lingering "SNIPPET:" if it was on the same line
            file_path = file_part.split("SNIPPET:")[0].strip()
        else:
            logger.warning(
                "LLM response contained no FILE: marker; no files identified",
                extra={"node": "researcher"},
            )

        files = [file_path] if file_path else []
        if files:
            logger.info(
                "Researcher identified files to modify",
                extra={"node": "researcher", "file_path": str(files)},
            )
        else:
            logger.warning(
                "Researcher found no files to modify — coder will receive an empty list",
                extra={"node": "researcher"},
            )

        if node_metric and metrics:
            metrics.end_node(node_metric, success=True)

        return {
            "files_to_modify": files,
            "research_summary": content,
        }

    except Exception as e:
        logger.error(
            "Researcher node failed: %s",
            str(e),
            exc_info=True,
            extra={"node": "researcher"},
        )
        if node_metric and metrics:
            metrics.record_error(node_metric, str(e))
            metrics.end_node(node_metric, success=False)
        return {
            "files_to_modify": [],
            "research_summary": f"Researcher error: {str(e)}",
        }
