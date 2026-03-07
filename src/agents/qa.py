from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.docker_sandbox import DockerSandbox
import os
import tempfile

QA_PROMPT = """You are a Lead QA Automation Engineer. You have been given a code fix: {code_fix}.

Create a unit test file that specifically targets the reported bug.
Run the test inside the Docker sandbox using the 'run_test_in_sandbox' tool.
If the test fails, provide the error logs back to the Coder Agent.
If the test passes, confirm the fix is ready for a Pull Request."""

def qa_node(state: ASEState) -> ASEState:
    """
    QA node to verify the fix inside a Docker sandbox.
    """
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    @tool
    def run_test_in_sandbox(test_code: str, file_name: str = "test_fix.py") -> str:
        """
        Writes the test code to the repo and runs it inside a Docker sandbox.
        """
        repo_dir = state.get("repo_path", "./dummy_repo")
        test_path = os.path.join(repo_dir, "tests", file_name)
        
        # Ensure tests directory exists
        os.makedirs(os.path.dirname(test_path), exist_ok=True)
        
        with open(test_path, 'w', encoding='utf-8') as f:
            f.write(test_code)
            
        sandbox = DockerSandbox()
        result = sandbox.run_tests(repo_dir, f"tests/{file_name}")
        
        state["test_passed"] = result.get("success", False)
        state["test_file_path"] = test_path
        state["test_logs"] = result.get("logs", "")
        
        return f"Success: {state['test_passed']}\nLogs:\n{state['test_logs']}"

    prompt = QA_PROMPT.format(code_fix=state.get("code_fix", ""))
    
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Please create and run the unit test.\n\nYou have access to the 'run_test_in_sandbox' tool. DO NOT use <function=> tags. Output your intent plainly.")
    ]
    
    response = llm.invoke(messages)
    
    state["current_agent"] = "qa"
    
    # Increment validation attempts
    attempts = state.get("validation_attempts", 0)
    state["validation_attempts"] = attempts + 1
    
    return state
