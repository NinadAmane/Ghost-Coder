import os
import subprocess
from github import Github
from typing import Dict, Any

class GitHubIntegration:
    def __init__(self, token: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.client = Github(self.token) if self.token else None

    def get_issue_details(self, repo_name: str, issue_number: int) -> Dict[str, Any]:
        """
        Fetch issue description from GitHub.
        Args:
            repo_name: Format 'owner/repo'
            issue_number: Issue ID.
        """
        if not self.client:
            raise ValueError("GITHUB_TOKEN is required to fetch issue details.")
            
        repo = self.client.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        
        return {
            "title": issue.title,
            "body": issue.body,
            "url": issue.html_url
        }

    def clone_repository(self, clone_url: str, dest_dir: str) -> bool:
        """
        Clones a repository to the local filesystem.
        """
        try:
            # We use subprocess to run git clone
            if not os.path.exists(dest_dir):
                subprocess.run(['git', 'clone', clone_url, dest_dir], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone repository: {e}")
            return False

    def create_pull_request(self, repo_name: str, branch_name: str, title: str, body: str, base_branch: str = "main") -> str:
        """
        Opens a PR on GitHub.
        """
        if not self.client:
            raise ValueError("GITHUB_TOKEN is required to create a PR.")
            
        repo = self.client.get_repo(repo_name)
        
        try:
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=base_branch
            )
            return pr.html_url
        except Exception as e:
            return f"Error creating PR: {str(e)}"
