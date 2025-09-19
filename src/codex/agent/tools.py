"""
Defines the suite of tools available to the AI agent.

Each function in this module represents a discrete capability that the agent
can execute. This includes interacting with the local file system.
"""

import os
import json
import subprocess
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WORKSPACE_PATH = PROJECT_ROOT / "workspace"
WORKSPACE_PATH.mkdir(exist_ok=True)

# --- Filesystem Tools ---

def list_files(directory: str = ".") -> str:
    """Lists all files and directories in the agent's workspace."""
    try:
        full_path = (WORKSPACE_PATH / directory).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        if not full_path.is_dir():
            return f"Error: Directory '{directory}' not found."
        return json.dumps(os.listdir(full_path))
    except Exception as e:
        return f"Error listing files: {e}"

def read_file(file_path: str) -> str:
    """Reads the content of a file from the agent's workspace."""
    try:
        full_path = (WORKSPACE_PATH / file_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        if not full_path.is_file():
            return f"Error: File '{file_path}' not found."
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(file_path: str, content: str) -> str:
    """Writes or overwrites a file in the agent's workspace."""
    try:
        full_path = (WORKSPACE_PATH / file_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Success: File '{file_path}' has been written."
    except Exception as e:
        return f"Error writing file: {e}"

def create_new_file(relative_file_path: str, content: str) -> str:
    """
    Creates a new file with content within the agent's workspace.
    This tool is sandboxed to the workspace.
    """
    try:
        # Sanitize the path to prevent traversal
        # Path.joinpath will correctly handle this on Windows and Linux
        full_path = (WORKSPACE_PATH / relative_file_path).resolve()

        # Security check: Ensure the final path is within the workspace
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied. Cannot create files outside the workspace."

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Success: File created at '{relative_file_path}' in workspace."
    except Exception as e:
        return f"Error creating new file: {e}"

def create_new_test_file(relative_file_path: str, content: str) -> str:
    """Creates a new test file in the 'tests/' subdirectory of the workspace."""
    try:
        base_name = Path(relative_file_path).name
        tests_dir = WORKSPACE_PATH / "tests"
        tests_dir.mkdir(exist_ok=True)
        safe_path = tests_dir / base_name
        safe_path.write_text(content, encoding="utf-8")
        return f"Success: Test file created at 'tests/{base_name}'."
    except Exception as e:
        return f"Error creating test file: {e}"

def run_tests() -> str:
    """
    Executes the pytest suite directly on the host machine inside the agent's workspace.
    """
    try:
        process = subprocess.run(
            ["pytest"],
            cwd=WORKSPACE_PATH,
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8',
            errors='replace'
        )
        output = f"--- STDOUT ---\n{process.stdout}\n\n--- STDERR ---\n{process.stderr}"
        return output
    except FileNotFoundError:
        return "Error: `pytest` command not found. Is pytest installed in the environment?"
    except Exception as e:
        return f"Error: An unexpected error occurred while running tests: {e}"

