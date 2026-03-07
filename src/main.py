import os
import argparse
import logging
from dotenv import load_dotenv
from src.graph import create_ase_graph

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Software Engineering System")
    parser.add_argument("--repo", type=str, help="The GitHub repository (e.g., owner/repo)")
    parser.add_argument("--issue", type=int, help="The GitHub issue number")
    args = parser.parse_args()

    logger.info("Initializing ASE System...")
    
    # Load environment variables from .env file
    load_dotenv()
    
    if not os.getenv("GROQ_API_KEY"):
        logger.warning("GROQ_API_KEY is not set. Groq LLM calls will fail.")
    if not os.getenv("GITHUB_TOKEN"):
        logger.error("GITHUB_TOKEN is not set. GitHub API calls will fail.")
        return

    repo_name = args.repo or os.getenv("GITHUB_REPOSITORY")
    issue_number_str = args.issue or os.getenv("ISSUE_NUMBER")

    if not repo_name or not issue_number_str:
        logger.error("Repository and issue number must be provided via CLI arguments (--repo, --issue) or environment variables (GITHUB_REPOSITORY, ISSUE_NUMBER).")
        return

    try:
        issue_number = int(issue_number_str)
    except ValueError:
        logger.error("Issue number must be an integer.")
        return
        
    logger.info(f"Welcome to the ASE System! Target: {repo_name}#{issue_number}")
    
    logger.info("Fetching issue details from GitHub...")
    from src.tools.github_tools import GitHubIntegration
    
    github_client = GitHubIntegration()
    try:
        issue_data = github_client.get_issue_details(repo_name, issue_number)
        logger.info(f"Issue Title: {issue_data['title']}")
    except Exception as e:
        logger.error(f"Failed to fetch issue: {e}")
        return
        
    logger.info("Cloning repository into local workspace...")
    workspace_dir = os.path.abspath(f"./.workspace/{repo_name.replace('/', '_')}")
    clone_url = f"https://github.com/{repo_name}.git"
    
    if not github_client.clone_repository(clone_url, workspace_dir):
        logger.error("Failed to clone repository. Exiting.")
        return
        
    graph = create_ase_graph()
    
    initial_state = {
        "github_issue_url": issue_data["url"],
        "issue_description": f"{issue_data['title']}\n\n{issue_data['body']}",
        "repo_path": workspace_dir,
        "validation_attempts": 0
    }
    
    logger.info(f"Starting multi-agent orchestration for issue #{issue_number}")
    
    # Execute graph
    final_state = None
    for event in graph.stream(initial_state):
        for node_name, node_state in event.items():
            logger.info(f"--- Finished node: {node_name} ---")
            final_state = node_state
            
    logger.info("="*50)
    logger.info("Orchestration complete.")
    
    if final_state:
        logger.info("[RESEARCHER SUMMARY]")
        logger.info(final_state.get("research_summary", "None"))
        
        logger.info("[CODER DRAFTED FIX]")
        logger.info(final_state.get("code_fix", "None"))
        
        logger.info("[QA TEST LOGS]")
        logger.info(final_state.get("test_logs", "None"))
        
        if final_state.get("test_passed"):
            logger.info("✅ Final Status: Tests PASSED. Ready for Pull Request.")
        else:
            logger.error(f"❌ Final Status: Tests FAILED after {final_state.get('validation_attempts')} attempts.")
    logger.info("="*50)

if __name__ == "__main__":
    main()
