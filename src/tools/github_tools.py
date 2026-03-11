import os
import subprocess
from github import Github
from typing import Dict, Any

class GitHubTool:
    def __init__(self, token: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.client = Github(self.token) if self.token else None

    def fetch_issue_details(self, issue_url: str) -> Dict[str, Any]:
        """
        Fetch issue title and body from a GitHub Issue URL.
        """
        if not self.client:
            raise ValueError("GITHUB_TOKEN is required.")
            
        # Parse URL: https://github.com/owner/repo/issues/number
        parts = issue_url.rstrip("/").split("/")
        owner = parts[-4]
        repo_name = parts[-3]
        issue_number = int(parts[-1])
        
        repo = self.client.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(number=issue_number)
        
        return {
            "title": issue.title,
            "body": issue.body,
            "url": issue.html_url
        }

    def clone_repository(self, issue_url: str, dest_dir: str) -> bool:
        """
        Clones the repository into a temporary directory.
        """
        parts = issue_url.rstrip("/").split("/")
        owner = parts[-4]
        repo_name = parts[-3]
        clone_url = f"https://github.com/{owner}/{repo_name}.git"
        
        try:
            if not os.path.exists(dest_dir):
                subprocess.run(['git', 'clone', clone_url, dest_dir], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone repository: {e}")
            return False

    def list_files(self, repo_dir: str) -> str:
        """
        Returns a tree-like string or list of all files in the repository.
        Ignores .git and common hidden folders.
        """
        files_list = []
        for root, dirs, files in os.walk(repo_dir):
            if '.git' in root or '__pycache__' in root:
                continue
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_dir)
                files_list.append(rel_path)
        return "\n".join(files_list)
        
    def read_file(self, repo_dir: str, file_path: str) -> str:
        """
        Reads a specific file for context.
        """
        full_path = os.path.join(repo_dir, file_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"

    def create_pull_request(self, repo_dir: str, branch_name: str, title: str, body: str) -> str:
        """
        Commits changes, pushes to a branch, and opens a PR.
        """
        if not self.token:
            return "Error: GITHUB_TOKEN not set."
            
        try:
            subprocess.run(['git', 'config', 'user.email', 'bot@example.com'], cwd=repo_dir, check=True)
            subprocess.run(['git', 'config', 'user.name', 'Agent Bot'], cwd=repo_dir, check=True)
            subprocess.run(['git', 'checkout', '-b', branch_name], cwd=repo_dir, check=True)
            subprocess.run(['git', 'add', '.'], cwd=repo_dir, check=True)
            subprocess.run(['git', 'commit', '--allow-empty', '-m', title], cwd=repo_dir, check=True)
            
            origin_url_bytes = subprocess.check_output(['git', 'config', '--get', 'remote.origin.url'], cwd=repo_dir)
            origin_url = origin_url_bytes.decode('utf-8').strip()
            
            if origin_url.startswith("https://"):
                auth_url = origin_url.replace("https://", f"https://x-access-token:{self.token}@")
            else:
                auth_url = origin_url
                
            push_cmd = ['git', 'push', '-u', auth_url, branch_name]
            result = subprocess.run(push_cmd, cwd=repo_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Failed to push branch. Error: {result.stderr.replace(self.token, '***')}")
                return "Failed to push to GitHub."
                
            # Now explicitly create the PR via API
            # Extract owner/repo from remote URL isn't strictly necessary if we parse it from origin_url, 
            # but let's assume standard behavior.
            owner_repo = "/".join(origin_url.split("/")[-2:]).replace(".git", "")
            repo = self.client.get_repo(owner_repo)
            
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base="main"
            )
            return pr.html_url
        except Exception as e:
            return f"Failed to create PR: {str(e)}"
