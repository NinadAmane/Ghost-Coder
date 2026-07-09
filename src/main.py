import os
import argparse
from dotenv import load_dotenv
from src.graph import create_ase_graph
from src.tools.github_tools import GitHubTool
from src.logging_config import get_logger
from src.metrics import RunMetrics

load_dotenv()

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ghost Coder: 3-Agent Core")
    parser.add_argument("issue_url", help="GitHub issue URL to fix")
    args = parser.parse_args()

    gh_tool = GitHubTool()
    issue_info = gh_tool.fetch_issue_details(args.issue_url)

    workspace_dir = os.path.join(os.getcwd(), "workspace_clones", "target_repo")
    os.makedirs(workspace_dir, exist_ok=True)

    gh_tool.clone_repository(args.issue_url, workspace_dir)

    initial_state = {
        "issue_url": args.issue_url,
        "issue_description": f"{issue_info['title']}\n\n{issue_info['body']}",
        "repo_path": workspace_dir,
        "files_to_modify": [],
        "research_summary": "",
        "updated_code": {},
        "test_logs": "",
        "test_passed": False,
        "test_explanation": "",
        "validation_attempts": 0
    }

    # Fresh metrics instance per run — no singleton, no cross-run leakage
    metrics = RunMetrics()
    metrics.start_run()

    graph = create_ase_graph(metrics=metrics)
    final_state = None

    for output in graph.stream(initial_state):
        for node_name, state_update in output.items():
            logger.info("Finished node: %s", node_name)
            final_state = state_update

    success = bool(final_state and final_state.get("test_passed"))
    metrics.end_run(success=success)

    if success:
        logger.info("Success! Issue fixed and tests passed.")
    else:
        logger.warning("Orchestration failed to fix the issue.")

    # Print metrics summary
    logger.info("Run metrics: %s", metrics.to_dict())


if __name__ == "__main__":
    main()
