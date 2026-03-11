from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.github_tools import GitHubTool
import json
import re

RESEARCHER_PROMPT = """You are a Software Researcher. Find the specific file and lines causing this issue. 
Output the filename and a code snippet of the problem area.

Issue Title: {issue_title}
Issue Body: {issue_body}

You have access to the repository file list below.
{file_list}

Select the most likely file from the list and specify the bug location. Do NOT output markdown text outside of a final JSON block.
Your final response MUST be a valid JSON object matching this schema exactly:
{{
    "files_to_modify": ["path/to/file.py"],
    "analysis": "Brief explanation of the problem."
}}"""

def researcher_node(state: ASEState) -> ASEState:
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    # Initialize Tool
    gh_tool = GitHubTool()
    
    # List files if we already cloned
    repo_dir = state["repo_path"]
    file_list = gh_tool.list_files(repo_dir)
    
    prompt = RESEARCHER_PROMPT.format(
        issue_title=state["issue_description"].split("\n")[0],
        issue_body=state["issue_description"],
        file_list=file_list
    )
    
    messages = [SystemMessage(content=prompt)]
    response = llm.invoke(messages)
    
    # Extract JSON
    content = response.content
    try:
        # Try to find a JSON block
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            result = json.loads(match.group())
            state["files_to_modify"] = result.get("files_to_modify", [])
    except Exception as e:
        print(f"Failed to parse researcher output: {e}")
        state["files_to_modify"] = []

    # Read the files targeted
    current_code = {}
    for f in state["files_to_modify"]:
        current_code[f] = gh_tool.read_file(repo_dir, f)
        
    state["current_code"] = current_code
    return state
