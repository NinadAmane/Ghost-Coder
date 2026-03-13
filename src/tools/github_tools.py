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
            basename = os.path.basename(root) if level > 0 else "."
            tree_output.append(f"{indent}{basename}/")
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

    def run_git_command(self, repo_path: str, command: list) -> str:
        """Executes a git command and returns the output."""
        try:
            result = subprocess.run(
                ['git'] + command, 
                cwd=repo_path, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            # Fallback to stdout or the generic error if stderr is somehow empty
            error_msg = e.stderr if e.stderr else (e.stdout or str(e))
            return f"Error: {error_msg}"

    def get_git_status(self, repo_path: str) -> str:
        """ Returns the current git status of the repository. """
        return self.run_git_command(repo_path, ['status'])

    def create_branch(self, repo_path: str, branch_name: str) -> str:
        """ Creates and checks out a new git branch. """
        return self.run_git_command(repo_path, ['checkout', '-b', branch_name])

    def stage_files(self, repo_path: str, files: list) -> str:
        """ Stages specific files for commit. """
        return self.run_git_command(repo_path, ['add'] + files)

    def commit_changes(self, repo_path: str, message: str) -> str:
        """ Commits staged changes with a message and explicit identity. """
        # Sets a generic identity just for this execution if needed
        env = os.environ.copy()
        env['GIT_AUTHOR_NAME'] = 'Ghost Coder Bot'
        env['GIT_AUTHOR_EMAIL'] = 'bot@ghostcoder.ai'
        env['GIT_COMMITTER_NAME'] = 'Ghost Coder Bot'
        env['GIT_COMMITTER_EMAIL'] = 'bot@ghostcoder.ai'
        
        try:
            result = subprocess.run(
                ['git', 'commit', '-m', message], 
                cwd=repo_path, 
                capture_output=True, 
                text=True, 
                check=True,
                env=env
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else (e.stdout or str(e))
            return f"Error: {error_msg}"

    def push_branch(self, repo_path: str, branch_name: str) -> str:
        """ Pushes the local branch to the remote origin. """
        return self.run_git_command(repo_path, ['push', '-u', 'origin', branch_name])

    def create_pull_request(self, issue_url: str, branch_name: str, title: str, body: str) -> str:
        """ Uses the GitHub API to open a Pull Request. """
        if not self.client:
            return "Error: GitHub Client Not Initialized"
        
        parts = issue_url.rstrip("/").split("/")
        owner, repo_name = parts[-4], parts[-3]
        
        try:
            repo = self.client.get_repo(f"{owner}/{repo_name}")
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=repo.default_branch
            )
            return pr.html_url
        except Exception as e:
            return f"Failed to create PR: {str(e)}"
