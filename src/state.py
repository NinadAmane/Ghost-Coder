from typing import TypedDict, List, Dict, Any

class ASEState(TypedDict):
    """
    Minimalist state for the 3-agent core.
    """
    issue_url: str
    issue_description: str
    repo_path: str
    
    # Researcher Output
    files_to_modify: List[str]
    research_summary: str
    
    # Coder Output
    updated_code: Dict[str, str] # mapping of filepath -> new content
    test_script: str
    
    # Tester Output
    test_logs: str
    test_passed: bool
    test_explanation: str
    
    # Metadata
    validation_attempts: int
