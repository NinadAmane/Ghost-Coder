import os
import json
import re
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.docker_sandbox import DockerSandbox

TESTER_PROMPT = """You are a QA Engineer. Create a small test script that reproduces the bug context to verify the fix. 
The test MUST exit with code 0 on success, or non-zero on failure. 

Issue: {issue_description}
Fix Details: We modified {files_modified}.

Output only a valid JSON object matching this schema exactly:
{{
    "test_filename": "test_fix.py",
    "test_code": "import sys\\n\\ndef test():\\n    pass\\n\\nif __name__ == '__main__':\\n    test()\\n    sys.exit(0)\\n"
}}"""

def tester_node(state: ASEState) -> ASEState:
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    files_modified = list(state.get("updated_code", {}).keys())
    
    prompt = TESTER_PROMPT.format(
        issue_description=state["issue_description"],
        files_modified=", ".join(files_modified)
    )
    
    messages = [SystemMessage(content=prompt)]
    response = llm.invoke(messages)
    
    # 1. Parse Test Code
    test_filename = "test_fix.py"
    test_code = ""
    try:
        match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if match:
            result = json.loads(match.group())
            test_filename = result.get("test_filename", "test_fix.py")
            test_code = result.get("test_code", "")
    except Exception as e:
        state["error_history"] = state.get("error_history", []) + [f"QA Generator parsing error: {e}"]
        state["test_passed"] = False
        return state
        
    if not test_code:
        state["error_history"] = state.get("error_history", []) + ["No test code generated."]
        state["test_passed"] = False
        return state

    # 2. Write test file in the REPO ROOT so imports work automatically
    repo_dir = state["repo_path"]
    test_path = os.path.join(repo_dir, test_filename)
    
    with open(test_path, 'w', encoding='utf-8') as f:
        f.write(test_code)

    # 3. Spin up Sandbox
    sandbox = DockerSandbox()
    result = sandbox.run_tests(repo_dir, test_filename)
    
    # 4. Process Results
    state["test_passed"] = result.get("success", False)
    
    if state["test_passed"]:
        print("\n✅ Test Passed!")
    else:
        logs = result.get("logs", "")
        # Create a tiny 1-2 sentence reflection for the coder so it's not complex
        short_logs = logs[-800:] if len(logs) > 800 else logs
        reflection_prompt = f"The test failed. Read the end of these logs and give a ONE sentence easy explanation of why it failed:\n{short_logs}"
        reflection = llm.invoke([SystemMessage(content=reflection_prompt)]).content
        
        state["error_history"] = [f"Test Script Failed! Simple Reason:\n{reflection}"]
        print(f"\n❌ Test Failed. Retrying...")
    
    return state
