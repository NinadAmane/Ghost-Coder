from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.docker_sandbox import DockerSandbox
import os
import tempfile

QA_PROMPT = """You are a Lead QA Automation Engineer. You have been given a code fix: {code_fix}.

Your job is to test this code fix. Look at the language of the code to determine how to test it.
- If Python, create a .py test file.
- If Rust, create a .rs test file.
- If JavaScript/TypeScript, create a .test.js or .test.ts file.

Run the test inside the dynamic Docker sandbox using the 'run_test_in_sandbox' tool. 
You MUST provide the 'test_code' and an appropriate 'file_name' (like 'test_fix.py' or 'test_fix.rs').
You may also provide a 'custom_command' if the default test runner for the language is not sufficient.
DO NOT use <function=> tags. Output your intent plainly.

If the test fails, provide the error logs back to the Coder Agent.
If the test passes, confirm the fix is ready for a Pull Request."""

def qa_node(state: ASEState) -> ASEState:
    """
    QA node to verify the fix inside a Docker sandbox.
    """
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    @tool
    def run_test_in_sandbox(test_code: str, file_name: str = "test_fix.py", custom_command: str = "") -> str:
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
        result = sandbox.run_tests(repo_dir=repo_dir, test_file_path=f"tests/{file_name}", custom_command=custom_command)
        
        state["test_passed"] = result.get("success", False)
        state["test_file_path"] = test_path
        state["test_logs"] = result.get("logs", "")
        
        return f"Success: {state['test_passed']}\nLogs:\n{state['test_logs']}"

    prompt = QA_PROMPT.format(code_fix=state.get("code_fix", ""))
    
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Please create and run the unit test.\n\nYou have access to the 'run_test_in_sandbox' tool. Output your intent plainly.")
    ]
    
    response = llm.invoke(messages)
    
    state["current_agent"] = "qa"
    
    # Increment validation attempts
    attempts = state.get("validation_attempts", 0)
    state["validation_attempts"] = attempts + 1
    
    return state
