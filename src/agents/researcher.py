import os
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.github_tools import GitHubTool

def researcher_node(state: ASEState):
    """
    SRS Researcher: Find the specific file and lines causing the issue.
    Output the filename and a code snippet of the problem area.
    """
    print("--- RESEARCHING ISSUE ---")
    llm = ChatGroq(model_name="llama-3.3-70b-versatile")
    gh_tool = GitHubTool()
    
    # 1. Get repo context (file tree)
    tree = gh_tool.list_files_tree(state["repo_path"])
    
    # 2. Ask LLM to pick files and explain why
    prompt = f"""
    Issue: {state['issue_description']}
    
    Repository Tree:
    {tree}
    
    Find the specific file and lines causing this issue. 
    Output the filename and a code snippet of the problem area.
    
    IMPORTANT: If the issue involves missing dependencies or third-party libraries (e.g., pandas, sklearn, numpy), 
    you MUST also include 'requirements.txt' in your FILE list, even if it does not exist in the tree.
    
    Format your response as:
    FILE: <path/to/file>
    SNIPPET:
    <code>
    """
    
    response = llm.invoke(prompt)
    content = response.content
    
    # Robust parsing logic
    file_path = ""
    if "FILE:" in content:
        # Extract everything after FILE: until the next newline or keyword
        file_part = content.split("FILE:")[1].split("\n")[0].strip()
        # Remove any lingering "SNIPPET:" if it was on the same line
        file_path = file_part.split("SNIPPET:")[0].strip()
    
    # Store the analysis in research_summary or similar (if we had it in state, we simplified it, let's check state)
    # The SRS wants "Files to Modify" as output.
    
    return {
        "files_to_modify": [file_path] if file_path else [],
        "research_summary": content # Storing the full analysis/snippet here
    }
