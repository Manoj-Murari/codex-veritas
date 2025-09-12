# src/codex_veritas/agent/tools.py

"""
Defines the suite of tools available to the AI agent.

Each function in this module represents a discrete capability that the agent
can execute, such as interacting with the file system or querying the code
graph. These tools form the agent's interface with its environment.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Literal

# --- Configuration ---
# Determine the project's root directory dynamically
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
WORKSPACE_PATH = PROJECT_ROOT / "workspace"
REPO_PATH = PROJECT_ROOT / "target_repo"
CODE_GRAPH_PATH = PROJECT_ROOT / "output" / "code_graph.json"

# --- Helper for Graph Tool ---
_code_graph_cache = None

def _get_code_graph() -> Dict[str, Any]:
    """Loads and caches the code graph from the JSON file."""
    global _code_graph_cache
    if _code_graph_cache is None:
        try:
            with open(CODE_GRAPH_PATH, 'r', encoding='utf-8') as f:
                _code_graph_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"--- ⚠️ WARNING: Code graph at {CODE_GRAPH_PATH} not found or invalid. ---")
            return {"nodes": [], "edges": []} # Return empty graph on error
    return _code_graph_cache

# --- Tool Definitions ---

def read_file(file_path: str) -> str:
    """Reads a file from the main code repository (target_repo)."""
    try:
        full_path = REPO_PATH.joinpath(file_path).resolve()
        if not str(full_path).startswith(str(REPO_PATH.resolve())):
            return "Error: Access denied. Cannot read files outside the target_repo."
        if not full_path.is_file():
            return f"Error: File '{file_path}' not found."
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def read_workspace_file(file_path: str) -> str:
    """Reads a file from the secure workspace."""
    try:
        full_path = WORKSPACE_PATH.joinpath(file_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied. Cannot read files outside the workspace."
        if not full_path.is_file():
            return f"Error: File '{file_path}' not found in workspace."
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading workspace file: {e}"

def list_files(directory_path: str) -> str:
    """Lists directory contents in the main code repository (target_repo)."""
    try:
        full_path = REPO_PATH.joinpath(directory_path).resolve()
        if not str(full_path).startswith(str(REPO_PATH.resolve())):
            return "Error: Access denied."
        if not full_path.is_dir():
            return f"Error: Directory '{directory_path}' not found."
        return json.dumps(os.listdir(full_path))
    except Exception as e:
        return f"Error listing directory: {e}"

def list_workspace_files(directory_path: str) -> str:
    """Lists directory contents in the secure workspace."""
    try:
        full_path = WORKSPACE_PATH.joinpath(directory_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        if not full_path.is_dir():
            return f"Error: Directory '{directory_path}' not found in workspace."
        return json.dumps(os.listdir(full_path))
    except Exception as e:
        return f"Error listing workspace directory: {e}"
        
def create_file(file_path: str, content: str) -> str:
    """Creates a new file in the secure workspace."""
    try:
        full_path = WORKSPACE_PATH.joinpath(file_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Success: File '{file_path}' created in the workspace."
    except Exception as e:
        return f"Error creating file: {e}"

def update_file(file_path: str, content: str) -> str:
    """Updates (overwrites) an existing file in the secure workspace."""
    try:
        full_path = WORKSPACE_PATH.joinpath(file_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        if not full_path.is_file():
            return f"Error: File '{file_path}' not found in workspace. Use create_file instead."
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Success: File '{file_path}' updated in the workspace."
    except Exception as e:
        return f"Error updating file: {e}"

def delete_file(file_path: str) -> str:
    """Deletes a file from the secure workspace."""
    try:
        full_path = WORKSPACE_PATH.joinpath(file_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        if not full_path.is_file():
            return f"Error: File '{file_path}' not found in workspace."
        os.remove(full_path)
        return f"Success: File '{file_path}' deleted from the workspace."
    except Exception as e:
        return f"Error deleting file: {e}"

def query_code_graph(entity_name: str, relationship: Literal['callers', 'callees']) -> str:
    """
    Queries the code graph to find relationships between code entities.
    - entity_name: The name of the function or class (e.g., 'create_app').
    - relationship: Either 'callers' (finds what calls the entity) or 'callees' (finds what the entity calls).
    """
    graph = _get_code_graph()
    target_node = next((n for n in graph.get('nodes', []) if n.get('name') == entity_name), None)

    if not target_node:
        return f"Error: Entity '{entity_name}' not found in the code graph."

    target_id = target_node['id']
    results = []
    
    if relationship == 'callers':
        caller_ids = {edge['source'] for edge in graph.get('edges', []) if edge.get('target') == target_id}
        results = [node for node in graph.get('nodes', []) if node.get('id') in caller_ids]
    elif relationship == 'callees':
        callee_ids = {edge['target'] for edge in graph.get('edges', []) if edge.get('source') == target_id}
        results = [node for node in graph.get('nodes', []) if node.get('id') in callee_ids]
    else:
        return "Error: Invalid relationship. Must be 'callers' or 'callees'."

    if not results:
        return f"No {relationship} found for '{entity_name}'."
        
    return json.dumps(results, indent=2)

def finish(final_answer: str) -> str:
    """
    Signals that the agent has completed its task and provides the final answer.
    """
    return final_answer
