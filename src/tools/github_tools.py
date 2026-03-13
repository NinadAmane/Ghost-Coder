import os
import subprocess
import requests
from github import Github
from dotenv import load_dotenv

load_dotenv()

class GitHubTool:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        if self.token:
            self.client = Github(self.token)
        else:
            self.client = None

    def fetch_issue_details(self, issue_url: str) -> dict:
        """ Fetches title and body of the issue. """
        if not self.client:
            return {
                "title": "Error: GitHub Client Not Initialized",
                "body": "Please ensure GITHUB_TOKEN is set in your .env file or environment."
            }
            
        parts = issue_url.rstrip("/").split("/")
        owner = parts[-4]
        repo_name = parts[-3]
        issue_number = int(parts[-1])
        
        try:
            repo = self.client.get_repo(f"{owner}/{repo_name}")
            issue = repo.get_issue(number=issue_number)
            
            return {
                "title": issue.title,
                "body": issue.body
            }
        except Exception as e:
            return {
                "title": "Error Fetching Issue",
                "body": str(e)
            }

    def clone_repository(self, issue_url: str, dest_dir: str) -> bool:
        """ Clones the repository safely using the provided token if available. """
        parts = issue_url.rstrip("/").split("/")
        owner = parts[-4]
        repo_name = parts[-3]
        
        # Build clone URL with token for seamless authentication (bypasses popups)
        if self.token:
            clone_url = f"https://{self.token}@github.com/{owner}/{repo_name}.git"
        else:
            clone_url = f"https://github.com/{owner}/{repo_name}.git"
        
        try:
            if os.path.exists(os.path.join(dest_dir, ".git")):
                return True
            
            if not os.path.exists(dest_dir) or not os.listdir(dest_dir):
                # Using subprocess and masking the URL in logs if possible, 
                # but since we are in a local env we just run it.
                subprocess.run(['git', 'clone', clone_url, dest_dir], check=True, capture_output=True)
                return True
            return False
        except Exception:
            return False

    def list_files_tree(self, repo_path: str) -> str:
        """
        Generates a tree-like string of the repository structure.
        Helpful for the Researcher to see the file tree of the target repository.
        """
        tree_output = []
        for root, dirs, files in os.walk(repo_path):
            if '.git' in dirs:
                dirs.remove('.git')
            if '.venv' in dirs:
                dirs.remove('.venv')
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
                
            level = root.replace(repo_path, '').count(os.sep)
            indent = ' ' * 4 * level
            tree_output.append(f"{indent}{os.path.basename(root)}/")
            sub_indent = ' ' * 4 * (level + 1)
            for f in files:
                tree_output.append(f"{sub_indent}{f}")
                
        return "\n".join(tree_output)

    def read_file(self, repo_path: str, file_path: str) -> str:
        """ Reads a file from the local repository for context. """
        full_path = os.path.join(repo_path, file_path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                return f"Error reading file: {str(e)}"
        return "File not found."
