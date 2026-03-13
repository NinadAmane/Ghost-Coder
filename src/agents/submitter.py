import time
from src.state import ASEState
from src.tools.github_tools import GitHubTool

def submit_pr_node(state: ASEState):
    """
    Final node to submit the pull request after successful testing.
    """
    print("--- SUBMITTING PULL REQUEST ---")
    try:
        gh_tool = GitHubTool()
        branch_name = f"ghost-coder-fix-{int(time.time())}"
        pr_url = gh_tool.create_pull_request(
            repo_dir=state["repo_path"],
            branch_name=branch_name,
            title="Automated Fix",
            body=f"Fixes {state['issue_url']}\n\nThis PR was autonomously generated and tested by Ghost Coder."
        )
        return {"pr_url": pr_url}
    except Exception as e:
        print(f"Failed to submit PR: {e}")
        return {"pr_url": f"Error: {str(e)}"}
