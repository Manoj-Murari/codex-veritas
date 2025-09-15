"""
The ASTParser Module: The Core Perception Engine.

This module is responsible for the heavy lifting of parsing Python code
into its constituent structural components. It uses the `tree-sitter` library
for its speed, robustness, and fault tolerance.

It is designed to be a pure, stateless utility. The core logic can be imported
and used by other parts of the system, such as the agent's analysis tools,
to parse code snippets on the fly.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

from tree_sitter import Parser
from tree_sitter_languages import get_language

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
parser_logger = logging.getLogger(__name__)

try:
    PYTHON_LANGUAGE = get_language('python')
    PARSER = Parser()
    PARSER.set_language(PYTHON_LANGUAGE)
except Exception as e:
    parser_logger.error(f"Failed to initialize tree-sitter Python language: {e}")
    PARSER = None

# --- Helper Functions ---

def _get_node_text(node, code_bytes: bytes) -> str:
    """Safely decodes the text of a tree-sitter node."""
    return code_bytes[node.start_byte:node.end_byte].decode('utf8', errors='ignore')

def _create_unique_id(relative_path_str: str, parts: List[str]) -> str:
    """Creates a standardized unique identifier for a code entity."""
    return f"{relative_path_str}::{'::'.join(parts)}"

def _get_node_ancestors(node):
    """Helper to walk up the tree from a given node."""
    curr = node.parent
    while curr:
        yield curr
        curr = curr.parent

# --- NEW: Core Parsing Logic (Refactored for Reusability) ---
def parse_code_to_components(code_bytes: bytes, relative_path_str: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses a byte string of code and returns its structural components.
    This is the core, reusable function.
    """
    if PARSER is None:
        parser_logger.error("Tree-sitter parser is not initialized.")
        return [], []

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    
    tree = PARSER.parse(code_bytes)
    root_node = tree.root_node

    if root_node.has_error:
        parser_logger.warning(f"Syntax error found in code snippet for {relative_path_str}, skipping.")
        return [], []

    file_id = relative_path_str
    nodes.append({
        "id": file_id, "type": "File", "name": Path(relative_path_str).name,
        "file_path": relative_path_str,
        "start_line": 1, "end_line": len(code_bytes.decode('utf8', 'ignore').splitlines())
    })

    query_str = """
    (class_definition name: (identifier) @class.name)
    (function_definition name: (identifier) @function.name)
    (import_statement name: (dotted_name) @import.name)
    (import_from_statement module_name: (dotted_name) @import.from name: (dotted_name) @import.name)
    """
    query = PYTHON_LANGUAGE.query(query_str)
    captures = query.captures(root_node)
    
    definitions = {}
    imports = []
    for node, capture_name in captures:
        if capture_name.endswith('.name'):
            if 'import' in capture_name:
                imports.append(node)
            else:
                definitions[node.id] = (node.parent, capture_name)

    for name_node_id, (def_node, def_type) in definitions.items():
        name_node = next((n for n, t in captures if n.id == name_node_id), None)
        if not name_node: continue

        if def_type == "class.name":
            class_name = _get_node_text(name_node, code_bytes)
            class_id = _create_unique_id(relative_path_str, [class_name])
            nodes.append({
                "id": class_id, "type": "Class", "name": class_name,
                "file_path": relative_path_str,
                "start_line": def_node.start_point[0] + 1, "end_line": def_node.end_point[0] + 1
            })
            edges.append({"source": file_id, "target": class_id, "type": "DEFINES"})
        
        elif def_type == "function.name":
            is_method = any(p.type == 'class_definition' for p in _get_node_ancestors(def_node))
            if is_method:
                parent_class_node = next((p for p in _get_node_ancestors(def_node) if p.type == 'class_definition'), None)
                if parent_class_node:
                    parent_name_node = parent_class_node.child_by_field_name("name")
                    if parent_name_node:
                        parent_class_name = _get_node_text(parent_name_node, code_bytes)
                        parent_class_id = _create_unique_id(relative_path_str, [parent_class_name])
                        method_name = _get_node_text(name_node, code_bytes)
                        method_id = _create_unique_id(relative_path_str, [parent_class_name, method_name])
                        nodes.append({
                            "id": method_id, "type": "Method", "name": method_name,
                            "file_path": relative_path_str,
                            "start_line": def_node.start_point[0] + 1, "end_line": def_node.end_point[0] + 1
                        })
                        edges.append({"source": parent_class_id, "target": method_id, "type": "DEFINES"})
            else:
                func_name = _get_node_text(name_node, code_bytes)
                func_id = _create_unique_id(relative_path_str, [func_name])
                nodes.append({
                    "id": func_id, "type": "Function", "name": func_name,
                    "file_path": relative_path_str,
                    "start_line": def_node.start_point[0] + 1, "end_line": def_node.end_point[0] + 1
                })
                edges.append({"source": file_id, "target": func_id, "type": "DEFINES"})

    for node in imports:
        import_name = _get_node_text(node, code_bytes)
        import_id = f"import::{import_name}"
        if not any(n['id'] == import_id for n in nodes):
            nodes.append({
                "id": import_id, "type": "Import", "name": import_name,
                "file_path": "external", "start_line": 0, "end_line": 0
            })
        edges.append({"source": file_id, "target": import_id, "type": "IMPORTS"})

    return nodes, edges


# --- Original file-based function (now a wrapper) ---
def parse_file_to_graph_components(file_path: Path, repo_root: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Reads a Python file and calls the core parser on its content.
    """
    relative_path_str = file_path.relative_to(repo_root).as_posix()
    try:
        with open(file_path, "rb") as f:
            code_bytes = f.read()
        return parse_code_to_components(code_bytes, relative_path_str)
    except FileNotFoundError:
        parser_logger.error(f"File not found: {file_path}")
        return [], []
    except Exception as e:
        parser_logger.error(f"An unexpected error occurred while reading {file_path}: {e}")
        return [], []

