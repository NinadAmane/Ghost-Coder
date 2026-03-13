from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.docker_sandbox import DockerSandbox

def tester_node(state: ASEState):
    """
    SRS Tester: Create a small test script that reproduces the bug. 
    Run it in the sandbox. If it fails, explain why to the coder.
    """
    print("--- TESTING FIX ---")
    llm = ChatGroq(model_name="llama-3.3-70b-versatile")
    sandbox = DockerSandbox()
    
    test_script_content = state.get("test_script", "")
    if not test_script_content:
        return {
            "test_logs": "No test script provided by Coder.",
            "test_passed": False,
            "test_explanation": "Coder failed to generate a test script.",
            "validation_attempts": state.get("validation_attempts", 0) + 1
        }
    
    # 1. Run in Docker Sandbox
    result = sandbox.run_test(state["repo_path"], test_script_content)
    
    passed = result["exit_code"] == 0
    logs = result["logs"]
    
    explanation = ""
    if not passed:
        # 3. Explain why it failed to the coder
        explain_prompt = f"""
        Test Script:
        {test_script_content}
        
        Test Logs:
        {logs}
        
        The test failed. Explain why it failed so the Coder can fix it.
        Be concise.
        """
        explanation_resp = llm.invoke(explain_prompt)
        explanation = explanation_resp.content.strip()
        
    print(f"Tests Passed: {passed}")
    return {
        "test_logs": logs,
        "test_passed": passed,
        "test_explanation": explanation, # Feedback for Coder
        "validation_attempts": state.get("validation_attempts", 0) + 1
    }
