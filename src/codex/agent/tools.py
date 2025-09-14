"""
The Agent's Toolbelt.

This module defines all the individual, secure tools that the AI agent is
allowed to execute. Each function represents a distinct capability.

The key design principle here is security and sandboxing. All file system
operations are strictly confined to a dedicated `workspace/` directory at the
project's root. The agent has no ability to read or write files outside of
this designated area, preventing it from accidentally modifying its own source
code or other critical project files.
"""

import os
import json
from pathlib import Path
from typing import List

# --- Configuration ---
# All file operations are sandboxed to this directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)


# --- Tool Definitions ---

def list_files(path: str = ".") -> str:
    """
    Lists the files and directories within the agent's workspace.

    Args:
        path: The relative path within the workspace to list. Defaults to the root.
    
    Returns:
        A JSON string containing a list of file and directory names.
    """
    try:
        base_path = WORKSPACE_DIR.joinpath(path).resolve()
        
        # Security Check: Ensure the path is within the workspace
        if not str(base_path).startswith(str(WORKSPACE_DIR.resolve())):
            return "Error: Access denied. Cannot list files outside the workspace."
            
        if not base_path.is_dir():
            return f"Error: '{path}' is not a valid directory."

        contents = [p.name for p in base_path.iterdir()]
        return json.dumps(contents)
    except Exception as e:
        return f"Error listing files: {e}"


def read_file(file_path: str) -> str:
    """
    Reads the contents of a file from the agent's workspace.

    Args:
        file_path: The relative path to the file within the workspace.

    Returns:
        The content of the file as a string, or an error message.
    """
    try:
        full_path = WORKSPACE_DIR.joinpath(file_path).resolve()

        # Security Check: Ensure the path is within the workspace
        if not str(full_path).startswith(str(WORKSPACE_DIR.resolve())):
            return "Error: Access denied. Cannot read files outside the workspace."
        
        if not full_path.is_file():
            return f"Error: File not found at '{file_path}'."

        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(file_path: str, content: str) -> str:
    """
    Writes or overwrites a file in the agent's workspace.

    Args:
        file_path: The relative path to the file within the workspace.
        content: The content to write to the file.

    Returns:
        A success or error message.
    """
    try:
        full_path = WORKSPACE_DIR.joinpath(file_path).resolve()
        
        # Security Check: Ensure the path is within the workspace
        if not str(full_path).startswith(str(WORKSPACE_DIR.resolve())):
            return "Error: Access denied. Cannot write files outside the workspace."

        # Ensure parent directories exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        full_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to '{file_path}'."
    except Exception as e:
        return f"Error writing file: {e}"
