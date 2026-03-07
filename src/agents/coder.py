from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from src.state import ASEState
import json

CODER_PROMPT = """You are a World-Class Software Engineer. Based on the Researcher's report: {research_summary}, implement a fix for the issue.

Write clean, modular, and PEP8-compliant code.
Ensure your fix does not break existing dependencies.
Output the full content of the modified files in JSON format: {{"file_path": "file_content"}}.
If the fix requires a new library, specify it for the QA agent."""

def coder_node(state: ASEState) -> ASEState:
    """
    Coder node to write the fix based on the researcher's summary.
    """
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    prompt = CODER_PROMPT.format(research_summary=state.get("research_summary", ""))
    
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Please provide the code fix in the required JSON format.")
    ]
    
    response = llm.invoke(messages)
    
    # In a full run, we would extract the JSON reliably.
    try:
        # Mocking extraction logic
        state["code_fix"] = response.content
        state["modified_files_content"] = {"src/main.py": "# Fixed code\nprint('fixed')"}
        state["new_dependencies"] = []
    except Exception as e:
        print(f"Error parsing coder output: {e}")
        
    state["current_agent"] = "coder"
    return state
