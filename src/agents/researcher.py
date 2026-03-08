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
You must invoke tools **natively** via the API.
DO NOT write tool calls in your text output! Do NOT write XML tags like `<function=...>`. Do NOT write raw JSON strings representing tools.
Just invoke the tool natively and wait for the response.

CRITICAL FINAL STEP:
Once you have gathered enough information, you MUST provide your final report in plain Markdown text WITHOUT making any tool calls. You must explicitly output a comprehensive, structured markdown narrative as your final message. Output your findings as a detailed, multi-section structured report."""

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

    # Remove CRITICAL TOOL FORMATTING completely and replace it with manual text-based JSON tools
    system_prompt = RESEARCHER_PROMPT.format(issue_description=state.get("issue_description", ""))
    system_prompt += """
    
CRITICAL TOOL USAGE INSTRUCTIONS:
You have access to the following tools:
1. {"name": "search_repo", "description": "Search the repository for a specific string.", "parameters": {"query": "string"}}
2. {"name": "list_repo_files", "description": "List files in the given directory or the root repository directory.", "parameters": {"directory_path": "string"}}
3. {"name": "read_repo_file", "description": "Read a file from the repository to analyze its code.", "parameters": {"file_path": "string"}}

To use a tool, you MUST output a raw JSON block like this and nothing else in your response:
{"name": "search_repo", "args": {"query": "the search term"}}

When you are done researching, you MUST output your final detailed Markdown report. Do NOT output a JSON block when you are done.
    """
    
    system_msg = SystemMessage(content=system_prompt)
    human_msg = HumanMessage(content="Please analyze the repository using your assigned tools.")
    
    logger.info("Researcher Manual JSON loop starting...")
    messages = [system_msg, human_msg]
    
    max_iterations = 6
    for i in range(max_iterations):
        response = llm.invoke(messages)
        messages.append(response)
        
        content = response.content.strip() if hasattr(response, "content") and response.content else ""
        
        # Check if the output looks like a JSON tool call request
        import json
        parsed_tool = None
        
        # Try finding JSON blocks
        if content.startswith("{") and "name" in content:
            try:
                # Naive parse
                parsed_tool = json.loads(content)
            except:
                # Attempt to extract if it has markdown formatting
                pass
                
        if not parsed_tool and "```json" in content:
            try:
                json_str = content.split("```json")[1].split("```")[0].strip()
                parsed_tool = json.loads(json_str)
            except:
                pass
                
        if not parsed_tool:
            # No tool call detected, assume it's the final output
            logger.info("No tool call detected. Breaking loop.")
            break
            
        tool_name = parsed_tool.get("name")
        tool_args = parsed_tool.get("args", {})
        
        logger.info(f"Researcher manually calling {tool_name} with args {tool_args}")
        
        if tool_name == "search_repo":
            tool_msg = search_repo.invoke(tool_args)
        elif tool_name == "list_repo_files":
            tool_msg = list_repo_files.invoke(tool_args)
        elif tool_name == "read_repo_file":
            tool_msg = read_repo_file.invoke(tool_args)
        else:
            tool_msg = "Error: Unknown tool."
            
        # Append observation as a human message so Groq doesn't expect a native tool history
        messages.append(HumanMessage(content=f"Observation from {tool_name}:\n{str(tool_msg)}\nWhat is your next step?"))
        
    final_output = messages[-1].content if hasattr(messages[-1], "content") and messages[-1].content else "Analysis finished."
    
    state["research_summary"] = final_output
    state["current_agent"] = "researcher"
    
    logger.info("Researcher bound_tools agent finished.")
    
    return state
