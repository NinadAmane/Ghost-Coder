from typing import TypedDict, List
from typing_extensions import Annotated
import operator

class ASEState(TypedDict):
    """
    State definition for the Simplified Autonomous Agent System.
    Passes the Current Code and Error History between agents.
    """
    issue_url: str
    issue_description: str
    repo_path: str
    
    # Researcher Output
    files_to_modify: List[str]
    current_code: dict[str, str] # filepath -> content
    
    # Coder Output
    updated_code: dict[str, str] # filepath -> modified content
    
    # Tester Output
    error_history: Annotated[list[str], operator.add]
    test_passed: bool
    
    # PR Submitter
    pr_url: str
