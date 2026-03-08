from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from src.state import ASEState
import json
import os
import logging

logger = logging.getLogger(__name__)

CODER_PROMPT = """You are a World-Class Polyglot Software Engineer. Based on the Researcher's report: {research_summary}, implement a fix for the issue.

IMPORTANT RULES:
1. First, provide a brief explanation of the changes you are making and your thought process.
2. Then, output the exact file modifications as a valid JSON object enclosed in a ```json code block.
3. JSON Format: {{"path/to/file.ext": "full file content here"}}
4. CRITICAL: Use '\\n' for newlines inside the JSON string. Do NOT use literal newlines.
5. EXTREMELY IMPORTANT: You MUST generate the FULL, COMPLETE, and CORRECT implementation. DO NOT generate placeholder functions, DO NOT use `pass`, DO NOT add comments like `# Actual implementation goes here`. You must write the actual, working code that fixes the issue.
6. Ensure the syntax is correct for the target language.
7. Do not include any conversational filler outside of the initial explanation."""

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
        
        # Basic structured validation: ensure it's a dict mapping strings to strings
        if not isinstance(modified_files, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in modified_files.items()):
            raise ValueError("Output JSON must be a dictionary mapping file paths to file contents.")

        state["code_fix"] = response.content # Store raw for UI
        state["modified_files_content"] = modified_files
        
        # Apply fixes to disk
        repo_path = state.get("repo_path", "")
        if repo_path:
            abs_repo_path = os.path.abspath(repo_path)
            for rel_path, file_content in modified_files.items():
                
                # Prevent absolute path traversal
                rel_path = rel_path.replace('\\', '/').lstrip('/')
                    
                abs_path = os.path.abspath(os.path.join(abs_repo_path, rel_path))
                
                # Check path traversal
                if not abs_path.startswith(abs_repo_path + os.sep) and abs_path != abs_repo_path:
                    logger.warning(f"Path traversal attempt detected and blocked: {rel_path}")
                    continue
                    
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)
                logger.info(f"Applied fix to {abs_path}")
                
    except Exception as e:
        logger.error(f"Error parsing coder output: {e}\nContent: {content}")
        state["code_fix"] = f"Error: Failed to parse or apply code fix JSON: {str(e)}"
        state["modified_files_content"] = {}

    state["current_agent"] = "coder"
    return state
