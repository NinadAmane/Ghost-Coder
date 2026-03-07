import os
from dotenv import load_dotenv
from src.graph import create_ase_graph

def main():
    print("Initializing ASE System...")
    
    # Load environment variables from .env file
    load_dotenv()
    
    if not os.getenv("GROQ_API_KEY"):
        print("WARNING: GROQ_API_KEY is not set. Groq LLM calls will fail.")
    if not os.getenv("GITHUB_TOKEN"):
        print("WARNING: GITHUB_TOKEN is not set. GitHub API calls will fail.")
        return
        
    print("Welcome to the ASE System!")
    repo_name = input("Enter the GitHub repository (e.g., owner/repo): ").strip()
    issue_number = int(input("Enter the GitHub issue number: ").strip())
    
    print("\n[+] Fetching issue details from GitHub...")
    from src.tools.github_tools import GitHubIntegration
    
    github_client = GitHubIntegration()
    try:
        issue_data = github_client.get_issue_details(repo_name, issue_number)
        print(f"Issue Title: {issue_data['title']}")
    except Exception as e:
        print(f"Failed to fetch issue: {e}")
        return
        
    print("\n[+] Cloning repository into local workspace...")
    workspace_dir = os.path.abspath(f"./.workspace/{repo_name.replace('/', '_')}")
    clone_url = f"https://github.com/{repo_name}.git"
    
    if not github_client.clone_repository(clone_url, workspace_dir):
        print("Failed to clone repository. Exiting.")
        return
        
    graph = create_ase_graph()
    
    initial_state = {
        "github_issue_url": issue_data["url"],
        "issue_description": f"{issue_data['title']}\n\n{issue_data['body']}",
        "repo_path": workspace_dir,
        "validation_attempts": 0
    }
    
    print(f"\nStarting multi-agent orchestration for issue #{issue_number}")
    
    # Execute graph
    final_state = None
    for event in graph.stream(initial_state):
        for node_name, node_state in event.items():
            print(f"--- Finished node: {node_name} ---")
            final_state = node_state
            
    print("\n" + "="*50)
    print("Orchestration complete.")
    
    if final_state:
        print("\n[RESEARCHER SUMMARY]")
        print(final_state.get("research_summary", "None"))
        
        print("\n[CODER DRAFTED FIX]")
        print(final_state.get("code_fix", "None"))
        
        print("\n[QA TEST LOGS]")
        print(final_state.get("test_logs", "None"))
        
        if final_state.get("test_passed"):
            print("\n✅ Final Status: Tests PASSED. Ready for Pull Request.")
        else:
            print(f"\n❌ Final Status: Tests FAILED after {final_state.get('validation_attempts')} attempts.")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
