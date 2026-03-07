from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from src.state import ASEState
from src.tools.file_tools import list_files, read_file
from src.tools.rag_tools import search_codebase
import json
import os
import logging

logger = logging.getLogger(__name__)

RESEARCHER_PROMPT = """You are an expert Senior Security and Systems Researcher. Your task is to explore the provided codebase and find the exact file and line numbers related to the reported issue: {issue_description}.

### MANDATORY REPORT GUIDELINES:
1. **Elaborate Analysis**: Provide a deep-dive into the codebase logic. Do not be brief.
2. **Structured Sections**:
   - **Root Cause**: Explain the logic flaw in detail.
   - **File & Line Locations**: List EVERY file path and the specific line ranges that need fixing.
   - **Technical Rationale**: Explain why these lines are problematic.

CRITICAL TOOL FORMATTING:
Do NOT output any tool calls using XML format or tags like `<function=...>`. You MUST use the native JSON tool calling format expected by the system. Never write raw `<function>` tags.

Output your findings as a detailed, multi-section structured report."""

def researcher_node(state: ASEState) -> ASEState:
    """
    Researcher node to analyze the repository and find the root cause of an issue.
    Uses a ReAct agent loop to iteratively call file-reading tools.
    """
    logger.info("Initializing Researcher ReAct Agent...")
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    repo_path = state.get("repo_path", "")
    
    @tool
    def search_repo(query: str) -> str:
        """
        Semantically searches the entire repository for a given query.
        Useful for finding implementations, usages, or logic related to the bug when you don't know the exact file name.
        """
        return search_codebase.invoke({"query": query, "repo_path": repo_path})

    @tool
    def list_repo_files(directory_path: str = ".") -> str:
        """
        List all files and directories in the specified path relative to the repository root.
        """
        full_dir = os.path.join(repo_path, directory_path)
        return list_files.invoke({"directory_path": full_dir})

    @tool
    def read_repo_file(file_path: str) -> str:
        """
        Read the contents of a specific file relative to the repository root.
        """
        full_path = os.path.join(repo_path, file_path)
        return read_file.invoke({"file_path": full_path})

    # Bind file reading and search tools
    tools = [search_repo, list_repo_files, read_repo_file]
    
    # We use bind_tools rather than create_react_agent so the LLM native tool-calling is engaged reliably
    llm_with_tools = llm.bind_tools(tools)
    
    # Simple explicit prompt that doesn't confuse Llama 3
    system_msg = SystemMessage(content=RESEARCHER_PROMPT.format(issue_description=state.get("issue_description", "")))
    
    human_msg = HumanMessage(content="Please analyze the repository using your tools. Call the tools natively.")
    
    logger.info("Researcher Tool-Calling loop starting...")
    
    # Basic reasoning loop for tool calls
    messages = [system_msg, human_msg]
    
    # Simple manual loop to prevent infinite hallucination rate-limits
    max_iterations = 5
    for i in range(max_iterations):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        
        if not response.tool_calls:
            break
            
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            logger.info(f"Researcher calling {tool_name} with args {tool_args}")
            
            if tool_name == "search_repo":
                tool_msg = search_repo.invoke(tool_args)
            elif tool_name == "list_repo_files":
                tool_msg = list_repo_files.invoke(tool_args)
            elif tool_name == "read_repo_file":
                tool_msg = read_repo_file.invoke(tool_args)
            else:
                tool_msg = "Error: Unknown tool."
                
            from langchain_core.messages import ToolMessage
            messages.append(ToolMessage(content=str(tool_msg), tool_call_id=tool_call["id"]))
            
    final_output = messages[-1].content if messages[-1].content else "Analysis finished. (No final text generated)"
    
    state["research_summary"] = final_output
    state["current_agent"] = "researcher"
    
    logger.info("Researcher ReAct agent finished.")
    
    return state
