from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from src.state import ASEState
from src.tools.file_tools import list_files, read_file
from src.tools.rag_tools import search_codebase
import json
import logging

logger = logging.getLogger(__name__)

RESEARCHER_PROMPT = """You are an expert Senior Security and Systems Researcher. Your task is to explore the provided codebase and find the exact file and line numbers related to the reported issue: {issue_description}.

You have access to tools to read the file system and perform semantic search across the codebase. Use them iteratively to find the exact code that needs fixing!

### MANDATORY REPORT GUIDELINES:
1. **Elaborate Analysis**: Provide a deep-dive into the codebase logic. Do not be brief.
2. **Bullet Points Only**: Use clearly structured bullet points for your findings.
3. **Structured Sections**:
   - **Root Cause**: Explain the logic flaw in detail.
   - **File & Line Locations**: List EVERY file path and the specific line ranges that need fixing.
   - **Technical Rationale**: Explain why these lines are problematic.

Do not repeat instructions or your internal thought process. Output your findings as a detailed, multi-section structured report."""

def researcher_node(state: ASEState) -> ASEState:
    """
    Researcher node to analyze the repository and find the root cause of an issue.
    Uses a ReAct agent loop to iteratively call file-reading tools.
    """
    logger.info("Initializing Researcher ReAct Agent...")
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    # Bind file reading and search tools
    tools = [list_files, read_file, search_codebase]
    
    prompt = RESEARCHER_PROMPT.format(issue_description=state.get("issue_description", ""))
    
    # Create the ReAct agent which handles the recursive tool-calling loop internally
    react_agent = create_react_agent(llm, tools=tools, state_modifier=prompt)
    
    human_msg = HumanMessage(content=f"Please analyze the repository at {state.get('repo_path')} for the issue. You must use your tools to actively read the codebase before giving an answer.")
    
    logger.info("Researcher ReAct agent starting execution loop...")
    # Invoke the agent graph. It will run until the LLM decides to stop calling tools and returns a final answer.
    result = react_agent.invoke({"messages": [human_msg]})
    
    # The final message in the state contains the agent's synthesized output
    final_output = result["messages"][-1].content
    
    state["research_summary"] = final_output
    state["current_agent"] = "researcher"
    
    logger.info("Researcher ReAct agent finished.")
    
    return state
