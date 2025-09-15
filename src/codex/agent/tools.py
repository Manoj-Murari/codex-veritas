"""
Defines the suite of tools available to the AI agent.

Each function in this module represents a discrete capability that the agent
can execute. This includes interacting with the local file system and performing
on-the-fly, structurally-aware code modifications.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

# --- Local Imports ---
from ..ingestion.parser import parse_code_to_components, _get_node_text
from ..query.engine import QueryEngine
from tree_sitter import Parser
from tree_sitter_languages import get_language

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
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

# --- NEW Structurally-Aware Refactoring Tool (Sprint 11 Fix) ---
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

        # 1. Read the file content
        with open(full_path, "rb") as f:
            code_bytes = f.read()
        lines = code_bytes.decode('utf-8').splitlines(True)

        # 2. Parse the code to find the function's location
        language = get_language('python')
        parser = Parser()
        parser.set_language(language)
        tree = parser.parse(code_bytes)
        root_node = tree.root_node

        # Find the specific function definition node
        func_node = None
        query = language.query("(function_definition name: (identifier) @func.name)")
        for node, capture_name in query.captures(root_node):
            if _get_node_text(node, code_bytes) == function_name:
                func_node = node.parent # The full (function_definition) node
                break
        
        if func_node is None:
            # Also check for methods inside classes
            class_query = language.query("(class_definition body: (block . (function_definition name: (identifier) @func.name)))")
            for node, capture_name in class_query.captures(root_node):
                 if _get_node_text(node, code_bytes) == function_name:
                    func_node = node.parent
                    break

        if func_node is None:
            return f"Error: Function or method '{function_name}' not found in '{file_path}'."

        # 3. Determine the correct line number and indentation
        func_body_node = func_node.child_by_field_name("body")
        if not func_body_node:
             return f"Error: Could not find function body for '{function_name}'."

        insertion_line_index = func_body_node.start_point[0]
        reference_line = lines[insertion_line_index]
        leading_whitespace = len(reference_line) - len(reference_line.lstrip(' '))
        indent_str = ' ' * leading_whitespace

        # 4. Format the new docstring
        formatted_docstring = f'{indent_str}"""{docstring}"""\n'

        # 5. Insert the docstring into the file's lines
        # We insert it right at the start of the function body
        new_lines = lines[:insertion_line_index + 1] + [formatted_docstring] + lines[insertion_line_index + 1:]
        # A simple check: if the line after the 'def' is a comment, we insert after that.
        if lines[func_node.start_point[0] + 1].strip().startswith('#'):
             new_lines = lines[:func_node.start_point[0] + 2] + [formatted_docstring] + lines[func_node.start_point[0] + 2:]
        else:
             new_lines = lines[:func_node.start_point[0] + 1] + [formatted_docstring] + lines[func_node.start_point[0] + 1:]


        with open(full_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
            
        return f"Success: Docstring added to function '{function_name}' in '{file_path}'."

    except Exception as e:
        return f"An unexpected error occurred: {e}"


# Analysis Tools (Not used in this sprint's test, but kept for future use)
def parse_code_snippet(code: str) -> str:
    """Parses a string of Python code and returns a summary of its structure."""
    try:
        nodes, _ = parse_code_to_components(code.encode('utf-8'), "snippet.py")
        summary = {
            "classes": [n['name'] for n in nodes if n['type'] == 'Class'],
            "functions": [n['name'] for n in nodes if n['type'] == 'Function'],
            "methods": [n['name'] for n in nodes if n['type'] == 'Method'],
        }
        return json.dumps(summary, indent=2)
    except Exception as e:
        return f"Error parsing code snippet: {e}"

def find_similar_code(query: str, db_path_str: str = "semantic_db") -> str:
    """Finds code snippets conceptually similar to the query."""
    try:
        db_path = Path(db_path_str)
        if not db_path.exists():
            return f"Error: Semantic database not found at '{db_path_str}'"
        temp_engine = QueryEngine(db_path=db_path)
        results = temp_engine.query_semantic(query, n_results=3)
        formatted_results = [
            {"name": r.get("metadata", {}).get("name", "N/A"), "file_path": r.get("metadata", {}).get("file_path", "N/A"), "similarity_score": 1 - r.get("distance", 1.0)}
            for r in results
        ]
        return json.dumps(formatted_results, indent=2)
    except Exception as e:
        return f"Error finding similar code: {e}"