import operator
from typing import Annotated, TypedDict, List, Dict, Any

class ASEState(TypedDict):
    """
    Represents the state of our multi-agent orchestration graph.
    """
    github_issue_url: str
    issue_description: str
    repo_path: str
    
    # Researcher Output
    research_summary: str
    files_to_modify: List[str]
    
    # Coder Output
    code_fix: str
    modified_files_content: Dict[str, str] # mapping of filepath -> new content
    new_dependencies: List[str]
    
    # QA Output
    test_file_path: str
    test_logs: str
    test_passed: bool
    
    # Orchestrator
    current_agent: str
    validation_attempts: int
