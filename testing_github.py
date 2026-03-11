import os
from github import Github
token = os.getenv("GITHUB_TOKEN")
g = Github(token)
issue_url = "https://github.com/NinadAmane/ghost-coder-test-repo/issues/1"
parts = issue_url.rstrip("/").split("/")
owner = parts[-4]
repo_name = parts[-3]
issue_number = int(parts[-1])
print("repo:", owner, repo_name)
repo = g.get_repo(f"{owner}/{repo_name}")
print("got repo")
issue = repo.get_issue(number=issue_number)
print("got issue:", issue.title)
print("done")
