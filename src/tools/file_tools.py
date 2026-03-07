import os
from langchain_core.tools import tool

@tool
def list_files(directory_path: str = ".") -> str:
    """
    List all files and directories in the specified path.
    Helpful for understanding the repository layout.
    
    Args:
        directory_path: The relative path to list files for. Defaults to current directory.
    """
    try:
        # Ignore common hidden/binary directories to prevent context bloat
        ignore_dirs = {'.git', '__pycache__', 'venv', '.env', '.venv', 'node_modules'}
        
        output = []
        for root, dirs, files in os.walk(directory_path):
            # Mutate dirs in-place to avoid walking ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            level = root.replace(directory_path, '').count(os.sep)
            indent = ' ' * 4 * (level)
            output.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                output.append(f"{subindent}{f}")
                
        return "\n".join(output)
    except Exception as e:
        return f"Error listing files: {str(e)}"

@tool
def read_file(file_path: str) -> str:
    """
    Read the contents of a specific file.
    
    Args:
        file_path: The relative path to the file to read.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Add line numbers for easier referencing by the LLM
            numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
            return "".join(numbered_lines)
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"

@tool
def apply_write_file(file_path: str, content: str) -> str:
    """
    Writes content to a file. Useful for applying code fixes.
    
    Args:
        file_path: The absolute path to the file to write.
        content: The new content of the file.
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing to file '{file_path}': {str(e)}"
