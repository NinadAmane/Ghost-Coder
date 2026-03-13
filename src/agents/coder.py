import os
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.github_tools import GitHubTool

def coder_node(state: ASEState):
    """
    SRS Coder: Based on research findings, rewrite the function to fix the bug.
    Provide the full content of the updated file.
    """
    print("--- CODING FIX ---")
    llm = ChatGroq(model_name="llama-3.3-70b-versatile")
    gh_tool = GitHubTool()
    
    updated_code = {}
    test_script = ""
    
    # 1. Generate Fixes
    for file_path in state["files_to_modify"]:
        current_content = gh_tool.read_file(state["repo_path"], file_path)
        
        failure_context = ""
        if state.get("test_explanation"):
            failure_context = f"\nPrevious Fix Failed. Feedback from Tester:\n{state['test_explanation']}\n"

        prompt = f"""
        Research Findings:
        {state['research_summary']}
        {failure_context}
        Issue: {state['issue_description']}
        File to Modify: {file_path}
        Current Content:
        {current_content}
        
        Task: Based on the researcher's findings and any previous failures, rewrite the function to fix the bug. 
        Provide the full content of the updated file.
        
        Return ONLY the complete new file content. No markdown, no explanation.
        """
        
        response = llm.invoke(prompt)
        new_content = response.content.strip()
        
        # Robustly strip markdown backticks if present
        if new_content.startswith("```"):
            lines = new_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            new_content = "\n".join(lines).strip()
        
        # Apply fix locally
        full_path = os.path.join(state["repo_path"], file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        updated_code[file_path] = new_content

    # 2. Generate Test Script (Reproduction & Verification)
    test_prompt = f"""
    Issue: {state['issue_description']}
    Fixed Code: {updated_code}
    
    Create a small test script (e.g., test_fix.py) that reproduces the bug 
    and verifies the fix. The script should use standard python with simple asserts.
    
    Return ONLY the complete python code for the test script. No markdown.
    """
    test_resp = llm.invoke(test_prompt)
    test_script = test_resp.content.strip()

    # Strip backticks from test script too
    if test_script.startswith("```"):
        lines = test_script.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        test_script = "\n".join(lines).strip()
        
    return {
        "updated_code": updated_code,
        "test_script": test_script
    }
