from typing import Dict
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from src.state import ASEState
import json
import re

CODER_PROMPT = """You are an Expert Software Engineer. Based on the researcher's findings, rewrite the function to fix the bug. Provide the full content of the updated file.

Issue: {issue_description}
Analysis: {files_to_modify}

Current Code:
{current_code_context}

Error History (if any):
{error_history}

Provide the full content of the updated file. You MUST output a JSON object EXACTLY like this:
{{
    "updated_file": "path/to/file.py",
    "updated_content": "import foo\\n\\ndef bar():\\n    pass\\n"
}}
"""

def coder_node(state: ASEState) -> ASEState:
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    current_code_context = ""
    if state.get("current_code"):
        for path, content in state["current_code"].items():
            current_code_context += f"\n--- {path} ---\n{content}\n"
            
    error_history = "\n".join(state.get("error_history", []))
            
    prompt = CODER_PROMPT.format(
        issue_description=state["issue_description"],
        files_to_modify=", ".join(state.get("files_to_modify", [])),
        current_code_context=current_code_context,
        error_history=error_history
    )
    
    messages = [SystemMessage(content=prompt)]
    response = llm.invoke(messages)
    
    # Extract JSON
    content = response.content
    try:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            result = json.loads(match.group())
            
            # Save the updated content
            updated_code = state.get("updated_code", {})
            file_name = result.get("updated_file")
            file_content = result.get("updated_content")
            
            if file_name and file_content:
                updated_code[file_name] = file_content
                
            state["updated_code"] = updated_code
            
            # Write to disk so tester can test it
            import os
            repo_path = state["repo_path"]
            full_path = os.path.join(repo_path, file_name)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(file_content)
                
    except Exception as e:
        print(f"Failed to parse coder output: {e}")
        state["updated_code"] = {"error": "Failed to parse"}
        
    return state
