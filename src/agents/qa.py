from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from src.state import ASEState
from src.tools.docker_sandbox import DockerSandbox
import os
import logging

logger = logging.getLogger(__name__)

QA_PROMPT = """You are a Lead QA Automation Engineer. You have been given a code fix: {code_fix}.

Your job is to test this code fix. Look at the language of the code to determine how to test it.
- If Python, create a .py test file.
- If Rust, create a .rs test file.
- If JavaScript/TypeScript, create a .test.js or .test.ts file.

Run the test inside the dynamic Docker sandbox using the 'run_test_in_sandbox' tool. 
You MUST provide the 'test_code' and an appropriate 'file_name' (like 'test_fix.py' or 'test_fix.rs').
You may also provide a 'custom_command' if the default test runner for the language is not sufficient.

If the test fails, use your reflection skills to summarize WHY it failed based on the logs, and explicitly state that it failed.
If the test passes, confirm the fix is ready for a Pull Request.

CRITICAL TOOL FORMATTING:
Do NOT output any tool calls using XML format or tags like `<function=...>`. You MUST use the native JSON tool calling format expected by the system. Never write raw `<function>` tags."""

def qa_node(state: ASEState) -> ASEState:
    """
    QA node to verify the fix inside a Docker sandbox via a ReAct Tool Loop.
    """
    logger.info("Initializing QA ReAct Agent...")
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    # We define the tool here so it can closure over `state` safely
    # Note: In a pure functional approach, you'd pass repo_dir explicitly 
    # but `state` is mutated by the tool to extract the success status.
    
    # We need to capture the results of the tool call independently because the ReAct 
    # agent only returns language history
    qa_results = {"test_passed": False, "test_file_path": "", "test_logs": ""}

    @tool
    def run_test_in_sandbox(test_code: str, file_name: str = "test_fix.py", custom_command: str = "") -> str:
        """
        Writes the test code to the repo and runs it inside a Docker sandbox.
        ALWAYS call this tool to verify the fix!
        """
        repo_dir = state.get("repo_path", "./dummy_repo")
        test_path = os.path.join(repo_dir, "tests", file_name)
        
        # Ensure tests directory exists
        os.makedirs(os.path.dirname(test_path), exist_ok=True)
        
        with open(test_path, 'w', encoding='utf-8') as f:
            f.write(test_code)
            
        sandbox = DockerSandbox()
        result = sandbox.run_tests(repo_dir=repo_dir, test_file_path=f"tests/{file_name}", custom_command=custom_command)
        
        qa_results["test_passed"] = result.get("success", False)
        qa_results["test_file_path"] = test_path
        qa_results["test_logs"] = result.get("logs", "")
        
        status_str = "PASSED" if qa_results["test_passed"] else "FAILED"
        return f"Test Execution {status_str}.\nLogs:\n{qa_results['test_logs']}"

    prompt = QA_PROMPT.format(code_fix=state.get("code_fix", ""))
    
    react_agent = create_react_agent(llm, tools=[run_test_in_sandbox], prompt=prompt)
    
    human_msg = HumanMessage(content="Please write a unit test to verify my code fix, and execute it using the sandbox tool.")
    
    logger.info("QA ReAct agent starting execution loop...")
    result = react_agent.invoke({"messages": [human_msg]})
    
    final_output = result["messages"][-1].content
    
    # Update global state with the trapped variables from the tool
    state["test_passed"] = qa_results["test_passed"]
    state["test_file_path"] = qa_results["test_file_path"]
    state["test_logs"] = final_output # The LLM's reflection on the logs
    
    # If it failed, append the reflection back to the research summary so the Coder can see it next loop
    if not state["test_passed"]:
        logger.warning("QA Failed. Appending reflection to research summary for Coder.")
        state["research_summary"] += f"\n\n--- QA FAILED (Attempt {state.get('validation_attempts', 0) + 1}) ---\n" + final_output
    
    state["current_agent"] = "qa"
    
    # Increment validation attempts
    attempts = state.get("validation_attempts", 0)
    state["validation_attempts"] = attempts + 1
    
    logger.info(f"QA ReAct agent finished. Passed: {state['test_passed']}")
    
    return state
