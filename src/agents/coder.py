import os
import re
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.github_tools import GitHubTool
from src.logging_config import get_logger
from src.metrics import RunMetrics

logger = get_logger(__name__)


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences (```...```) from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_search_replace_blocks(response_text: str) -> list[dict]:
    """
    Parse SEARCH/REPLACE blocks from LLM output.

    Expected format:
        <<<<<<< SEARCH
        old code
        =======
        new code
        >>>>>>> REPLACE

    Returns a list of dicts with 'search' and 'replace' keys.
    """
    blocks = []
    pattern = r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE'
    matches = re.findall(pattern, response_text, re.DOTALL)
    for search_text, replace_text in matches:
        blocks.append({
            "search": search_text,
            "replace": replace_text,
        })
    return blocks


def _apply_search_replace(original_content: str, blocks: list[dict]) -> str:
    """
    Apply SEARCH/REPLACE blocks to the original file content.
    Each block's 'search' text is replaced with its 'replace' text exactly once.
    Returns the modified content.
    """
    content = original_content
    for block in blocks:
        if block["search"] in content:
            content = content.replace(block["search"], block["replace"], 1)
        else:
            # Try a more forgiving match by stripping trailing whitespace per line
            search_lines = [l.rstrip() for l in block["search"].splitlines()]
            content_lines = [l.rstrip() for l in content.splitlines()]

            search_str = "\n".join(search_lines)
            content_str = "\n".join(content_lines)

            if search_str in content_str:
                result = content_str.replace(search_str, block["replace"], 1)
                # Restore original line endings
                content = result
            else:
                logger.warning(
                    "SEARCH block not found in file, skipping this block",
                    extra={"node": "coder"},
                )
    return content


def coder_node(state: ASEState, metrics: RunMetrics | None = None):
    """
    SRS Coder: Based on research findings, generate precise SEARCH/REPLACE
    patches to fix the bug. Falls back to full-file rewrite if needed.
    """
    node_metric = metrics.start_node("coder") if metrics else None
    logger.info("Coder node started", extra={"node": "coder"})

    try:
        # Guard: if researcher found no files, return early with explanation
        if not state.get("files_to_modify"):
            msg = "No files to modify — researcher did not identify any target files."
            logger.error(msg, extra={"node": "coder"})
            if node_metric and metrics:
                metrics.record_error(node_metric, msg)
                metrics.end_node(node_metric, success=False)
            return {
                "updated_code": {},
                "test_script": "",
            }

        llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            api_key=state.get("groq_api_key"),
        )
        gh_tool = GitHubTool(token=state.get("github_token"))

        updated_code = {}
        test_script = ""

        # 1. Generate Fixes using SEARCH/REPLACE blocks
        for file_path in state["files_to_modify"]:
            
            # Strip leading repo basename from file_path if it exists
            # (prevents nested directory bug when LLM includes repo name in path)
            repo_basename = os.path.basename(
                state["repo_path"].rstrip(os.sep)
            )
            clean_file_path = file_path
            if file_path.startswith(f"{repo_basename}/"):
                clean_file_path = file_path[len(repo_basename) + 1 :]
            elif file_path.startswith(f"./{repo_basename}/"):
                clean_file_path = file_path[len(repo_basename) + 3 :]
                
            current_content = gh_tool.read_file(state["repo_path"], clean_file_path)

            # Check if the file was actually found
            if current_content == "File not found.":
                logger.warning(
                    "File not found in repo, skipping: %s",
                    file_path,
                    extra={"node": "coder", "file_path": file_path},
                )
                continue

            failure_context = ""
            if state.get("test_explanation"):
                failure_context = (
                    f"\nPrevious Fix Failed. Feedback from Tester:\n"
                    f"{state['test_explanation']}\n"
                )

            prompt = f"""
Research Findings:
{state['research_summary']}
{failure_context}
Issue: {state['issue_description']}
File to Modify: {file_path}
Current Content:
{current_content}

Task: Fix the bug described above using precise SEARCH/REPLACE blocks.
Each block identifies the exact lines to change and provides the replacement.

Rules:
- Output one or more SEARCH/REPLACE blocks.
- The SEARCH section must match the current file content EXACTLY (including indentation).
- The REPLACE section is the new code that will replace the search section.
- Only include the lines that need to change (plus a few surrounding lines for context).
- Do NOT output the entire file.

If the file to modify is 'requirements.txt', just return the full file content (one dependency per line).

Format each block exactly like this:

<<<<<<< SEARCH
exact old code from the file
=======
your new replacement code
>>>>>>> REPLACE

Output ONLY the SEARCH/REPLACE blocks. No explanation, no markdown fences.
"""

            response = llm.invoke(prompt)
            raw_output = _strip_markdown_fences(response.content.strip())

            # Track LLM token usage
            if node_metric and hasattr(response, "response_metadata"):
                token_usage = response.response_metadata.get(
                    "token_usage", {}
                )
                if metrics and token_usage:
                    metrics.record_llm_tokens(
                        node_metric,
                        prompt_tokens=token_usage.get("prompt_tokens", 0),
                        completion_tokens=token_usage.get(
                            "completion_tokens", 0
                        ),
                    )

            # Try parsing SEARCH/REPLACE blocks
            blocks = _parse_search_replace_blocks(raw_output)

            if blocks:
                # Apply patches to the original content
                new_content = _apply_search_replace(current_content, blocks)
                logger.info(
                    "Applied %d SEARCH/REPLACE block(s) to %s",
                    len(blocks),
                    file_path,
                    extra={"node": "coder", "file_path": file_path},
                )
            else:
                # Fallback: LLM returned full file content instead of blocks
                logger.warning(
                    "No SEARCH/REPLACE blocks found, falling back to full "
                    "rewrite for %s",
                    file_path,
                    extra={"node": "coder", "file_path": file_path},
                )
                new_content = raw_output

            full_path = os.path.abspath(
                os.path.join(state["repo_path"], clean_file_path)
            )

            # Security Check: Ensure path is within repo_path
            if not full_path.startswith(os.path.abspath(state["repo_path"])):
                logger.error(
                    "SECURITY: directory traversal detected for path: %s",
                    file_path,
                    extra={"node": "coder", "file_path": file_path},
                )
                if node_metric and metrics:
                    metrics.record_error(
                        node_metric,
                        f"Directory traversal blocked: {file_path}",
                    )
                continue

            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            updated_code[clean_file_path] = new_content

        # 2. Generate Test Script (Reproduction & Verification)
        test_prompt = f"""
Issue: {state['issue_description']}
Fixed Code: {updated_code}

Create a small test script (e.g., test_fix.py) that reproduces the bug
and verifies the fix. The script should use standard python with simple asserts.

Return ONLY the complete python code for the test script. No markdown.
"""
        test_resp = llm.invoke(test_prompt)
        test_script = _strip_markdown_fences(test_resp.content.strip())

        # Track LLM token usage for test generation
        if node_metric and hasattr(test_resp, "response_metadata"):
            token_usage = test_resp.response_metadata.get(
                "token_usage", {}
            )
            if metrics and token_usage:
                metrics.record_llm_tokens(
                    node_metric,
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get(
                        "completion_tokens", 0
                    ),
                )

        if node_metric and metrics:
            metrics.end_node(node_metric, success=True)

        return {
            "updated_code": updated_code,
            "test_script": test_script,
        }

    except Exception as e:
        logger.error(
            "Coder node failed: %s",
            str(e),
            exc_info=True,
            extra={"node": "coder"},
        )
        if node_metric and metrics:
            metrics.record_error(node_metric, str(e))
            metrics.end_node(node_metric, success=False)
        return {
            "updated_code": state.get("updated_code", {}),
            "test_script": "",
        }
