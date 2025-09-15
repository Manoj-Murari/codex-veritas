"""
Defines the suite of tools available to the AI agent.

Each function in this module represents a discrete capability that the agent
can execute. This includes interacting with the local file system and performing
on-the-fly, structurally-aware code modifications.
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Dict, Any

# --- Local Imports ---
from ..ingestion.parser import _get_node_text
from tree_sitter import Parser
from tree_sitter_languages import get_language

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
    Creates a new file with the specified content at a path relative to the project root.
    If parent directories do not exist, they will be created.

    Args:
        relative_file_path: The full path for the new file, relative to the project root (e.g., 'src/codex/agent/stats_tool.py').
        content: The complete source code or text to write into the new file.
    """
    try:
        full_path = Path.cwd() / relative_file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')
        return f"Success: File '{relative_file_path}' created successfully."
    except Exception as e:
        return f"Error: An unexpected error occurred while creating file '{relative_file_path}': {e}"

def create_new_test_file(relative_file_path: str, content: str) -> str:
    """
    Creates a new test file in the 'tests/' subdirectory of the workspace.
    This tool is sandboxed and cannot write files outside of the 'tests/' directory.

    Args:
        relative_file_path: The path for the new file, relative to the 'tests/' directory (e.g., 'test_my_new_module.py').
        content: The complete source code for the test file.
    """
    try:
        tests_dir = (WORKSPACE_PATH / "tests").resolve()
        tests_dir.mkdir(exist_ok=True)

        if ".." in Path(relative_file_path).parts:
             return "Error: Path traversal ('..') is not allowed."

        full_path = (tests_dir / relative_file_path).resolve()

        if not str(full_path).startswith(str(tests_dir)):
            return f"Error: Security violation. Attempted to write file outside of the designated 'tests' directory."

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')
        
        workspace_relative_path = full_path.relative_to(WORKSPACE_PATH)
        return f"Success: Test file created at '{workspace_relative_path}'."

    except Exception as e:
        return f"Error: An unexpected error occurred while creating test file: {e}"

# --- NEW: Test Execution Tool (Sprint 16) ---
def run_tests() -> str:
    """
    Executes the pytest suite inside the agent's workspace and captures the output.
    This tool requires no arguments.

    Returns:
        A string containing the combined stdout and stderr from the pytest command.
    """
    try:
        # Execute pytest within the WORKSPACE_PATH directory to ensure correct test discovery.
        # We capture both stdout and stderr to provide a complete picture to the agent.
        process = subprocess.run(
            ["pytest"],
            cwd=WORKSPACE_PATH,
            capture_output=True,
            text=True, # Ensure stdout/stderr are decoded as text
            check=False # Prevent raising an exception for non-zero (failing test) exit codes
        )
        
        # Combine stdout and stderr for a comprehensive report.
        output = f"--- STDOUT ---\n{process.stdout}\n\n--- STDERR ---\n{process.stderr}"
        
        return output

    except FileNotFoundError:
        return "Error: `pytest` command not found. Is pytest installed in the environment?"
    except Exception as e:
        return f"Error: An unexpected error occurred while running tests: {e}"

# --- Structurally-Aware Refactoring Tool ---
def add_docstring_to_function(file_path: str, function_name: str, docstring: str) -> str:
    """
    Adds a docstring to a specific function in a Python file, handling indentation.
    This tool is structurally aware and does not require line numbers.

    Args:
        file_path: The path to the file in the workspace.
        function_name: The name of the function to add the docstring to.
        docstring: The new docstring content (without triple quotes).
    """
    try:
        full_path = (WORKSPACE_PATH / file_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        if not full_path.is_file():
            return f"Error: File '{file_path}' not found."

        with open(full_path, "rb") as f:
            code_bytes = f.read()
        lines = code_bytes.decode('utf-8').splitlines(True)

        language = get_language('python')
        parser = Parser()
        parser.set_language(language)
        tree = parser.parse(code_bytes)
        root_node = tree.root_node

        func_node = None
        query = language.query("(function_definition name: (identifier) @func.name)")
        for node, capture_name in query.captures(root_node):
            if _get_node_text(node, code_bytes) == function_name:
                func_node = node.parent
                break
        
        if func_node is None:
            class_query = language.query("(class_definition body: (block . (function_definition name: (identifier) @func.name)))")
            for node, capture_name in class_query.captures(root_node):
                if _get_node_text(node, code_bytes) == function_name:
                    func_node = node.parent
                    break

        if func_node is None:
            return f"Error: Function or method '{function_name}' not found in '{file_path}'."

        func_body_node = func_node.child_by_field_name("body")
        if not func_body_node:
            return f"Error: Could not find function body for '{function_name}'."

        insertion_line_index = func_body_node.start_point[0]
        reference_line = lines[insertion_line_index]
        leading_whitespace = len(reference_line) - len(reference_line.lstrip(' '))
        indent_str = ' ' * leading_whitespace

        formatted_docstring = f'{indent_str}"""{docstring}"""\n'

        if lines[func_node.start_point[0] + 1].strip().startswith('#'):
            new_lines = lines[:func_node.start_point[0] + 2] + [formatted_docstring] + lines[func_node.start_point[0] + 2:]
        else:
            new_lines = lines[:func_node.start_point[0] + 1] + [formatted_docstring] + lines[func_node.start_point[0] + 1:]

        with open(full_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
            
        return f"Success: Docstring added to function '{function_name}' in '{file_path}'."

    except Exception as e:
        return f"An unexpected error occurred: {e}"

