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
            
    def commit_and_push_changes(self, repo_dir: str, branch_name: str, commit_message: str) -> bool:
        """
        Commits all local changes in the repository and pushes them to a new branch.
        """
        if not self.token:
            print("Cannot push: GITHUB_TOKEN is not set.")
            return False
            
        try:
            # We configure git minimally in case it's a fresh docker container
            subprocess.run(['git', 'config', 'user.email', 'ghost-coder@example.com'], cwd=repo_dir, check=True)
            subprocess.run(['git', 'config', 'user.name', 'Ghost Coder Bot'], cwd=repo_dir, check=True)
            
            # Checkout new branch
            subprocess.run(['git', 'checkout', '-b', branch_name], cwd=repo_dir, check=True)
            
            # Add and commit
            subprocess.run(['git', 'add', '.'], cwd=repo_dir, check=True)
            
            # We allow empty commits just in case, though ideally there are changes
            subprocess.run(['git', 'commit', '--allow-empty', '-m', commit_message], cwd=repo_dir, check=True)
            
            # Formulate the push URL with the token
            # Note: repo_dir basename is the generic owner_repo folder, but we actually 
            # need the github origin url. We can get it from git config.
            origin_url_bytes = subprocess.check_output(['git', 'config', '--get', 'remote.origin.url'], cwd=repo_dir)
            origin_url = origin_url_bytes.decode('utf-8').strip()
            
            # origin_url format: https://github.com/owner/repo.git
            if origin_url.startswith("https://"):
                auth_url = origin_url.replace("https://", f"https://x-access-token:{self.token}@")
            else:
                auth_url = origin_url
                
            # Push
            push_cmd = ['git', 'push', '-u', auth_url, branch_name]
            # Use capture_output to avoid leaking the token to stdout blindly
            result = subprocess.run(push_cmd, cwd=repo_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Failed to push branch. Error: {result.stderr.replace(self.token, '***')}")
                return False
                
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to commit/push repository: {e}")
            return False
