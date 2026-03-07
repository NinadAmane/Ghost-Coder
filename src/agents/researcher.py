from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from src.state import ASEState
from src.tools.file_tools import list_files, read_file
import json

RESEARCHER_PROMPT = """You are an expert Senior Security and Systems Researcher. Your task is to explore the provided codebase and find the exact file and line numbers related to the reported issue: {issue_description}.

Use the 'list_files' tool to see the directory structure.
Use 'read_file' to examine logic.
Do not attempt to fix the code.

Output a summary of the root cause and the file paths that need modification."""

def researcher_node(state: ASEState) -> ASEState:
    """
    Researcher node to analyze the repository and find the root cause of an issue.
    """
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    # Bind file reading tools
    tools = [list_files, read_file]
    llm_with_tools = llm.bind_tools(tools)
    
    prompt = RESEARCHER_PROMPT.format(issue_description=state.get("issue_description", ""))
    
    # For a real implementation, we would use an AgentExecutor or loop to handle
    # intermediate tool calls. Here we do an initial pass for demonstration.
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Please analyze the repository at {state.get('repo_path')} for the issue.\n\nYou have access to the following tools: 'list_files', 'read_file'.")
    ]
    
    response = llm.invoke(messages)
    
    # Normally we would loop and execute tool calls here.
    # We will simulate the output logic based on final LLM generation.
    
    state["research_summary"] = response.content if response.content else "Identified the issue via tool calls."
    # We would parse actual files from response, hardcoding one for the prototype
    state["files_to_modify"] = ["src/main.py"] 
    state["current_agent"] = "researcher"
    
    return state
