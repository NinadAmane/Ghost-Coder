import os
from github import Github
from dotenv import load_dotenv

load_dotenv()

def create_dummy_repo():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set.")
        return

    try:
        g = Github(token)
        user = g.get_user()
        
        repo_name = "ghost-coder-test-repo"
        print(f"Creating repository: {repo_name}...")
        
        # Check if repo exists
        try:
            repo = user.get_repo(repo_name)
            print("Repository already exists. Using existing repo.")
        except Exception:
            # Create a private repository for testing
            repo = user.create_repo(
                name=repo_name,
                description="A dummy repository for testing Ghost Coder orchestration",
                private=True,
                auto_init=True # Initializes with a README
            )
            print("Repository created.")

        # Create a buggy file
        file_path = "calculator.py"
        buggy_content = '''def add(a, b):
    # TODO: fix this bug
    return a - b

def subtract(a, b):
    return a - b
'''     
        commit_message = "Initial commit with a buggy calculator"
        
        try:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, commit_message, buggy_content, contents.sha)
            print(f"Updated {file_path}")
        except Exception:
            repo.create_file(file_path, commit_message, buggy_content)
            print(f"Created {file_path}")

        # Create an issue
        issue_title = "Bug in calculator: add function is subtracting"
        issue_body = """I noticed that when I call the `add` function in `calculator.py`, it actually subtracts the two numbers instead of adding them.

Can you please fix the `add` function so that it returns `a + b`?
"""
        issue = repo.create_issue(title=issue_title, body=issue_body)
        print(f"\n--- SUCCESS ---")
        print(f"Issue created at: {issue.html_url}")
        print(f"\nTo test the agent, run:")
        print(f"uv run src/main.py {issue.html_url}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    create_dummy_repo()
