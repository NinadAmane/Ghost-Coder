import os
from dotenv import load_dotenv
load_dotenv()

from src.graph import create_ase_graph

def run():
    graph = create_ase_graph()
    
    initial_state = {
        "repo_path": "g:\\Multi-Agent-Orchestration-Project\\.workspace\\Harry-kp_vortix",
        "issue_description": "Test issue 139",
        "files_to_modify": [],
        "code_fix": "",
        "validation_attempts": 0,
        "test_passed": False,
        "test_file_path": "",
        "test_logs": "",
        "research_summary": "",
        "current_agent": "researcher"
    }

    print("Starting graph...")
    try:
        # Note: if the repo doesn't exist locally, it might fail. But let's see.
        final_state = None
        for event in graph.stream(initial_state):
            print(event)
        print("Success.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run()
