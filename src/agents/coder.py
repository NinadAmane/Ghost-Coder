from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from src.state import ASEState
import json
import os

CODER_PROMPT = """You are a World-Class Polyglot Software Engineer. Based on the Researcher's report: {research_summary}, implement a fix for the issue.

IMPORTANT RULES:
1. Output ONLY a valid JSON object. 
2. Format: {{"path/to/file.ext": "full file content here"}}
3. CRITICAL: Use '\\n' for newlines inside the JSON string. Do NOT use literal newlines.
4. Ensure the syntax is correct for the target language (Rust, Python, Node, etc.).
5. Do not include any conversational filler."""

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
    content = response.content
    
    # Try to extract JSON between backticks if present
    if "```json" in content:
        content = content.split("```json")[-1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[-1].split("```")[0].strip()

    try:
        # Use strict=False to handle literal newlines if a LLM makes a mistake
        modified_files = json.loads(content, strict=False)
        state["code_fix"] = response.content # Store raw for UI
        state["modified_files_content"] = modified_files
        
        # Apply fixes to disk
        repo_path = state.get("repo_path", "")
        if repo_path:
            for rel_path, file_content in modified_files.items():
                abs_path = os.path.join(repo_path, rel_path)
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)
                print(f"Applied fix to {abs_path}")
                
    except Exception as e:
        print(f"Error parsing coder output: {e}\nContent: {content}")
        state["code_fix"] = f"Error: Failed to parse or apply code fix JSON: {str(e)}"
        state["modified_files_content"] = {}

    state["current_agent"] = "coder"
    return state
