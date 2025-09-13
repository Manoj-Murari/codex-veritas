# src/codex/ingestion/parser.py

"""
The ASTParser Module: The Core Perception Engine.

This module is responsible for the heavy lifting of parsing a single Python file
into its constituent structural components. It uses the `tree-sitter` library
for its speed, robustness, and fault tolerance.

The primary function, `parse_file_to_graph_components`, is designed to be a pure,
stateless function that takes a file path and returns the nodes and edges found
within that file. It is critically designed to be fault-tolerant; if a file
contains a syntax error, it will log the issue and return empty lists, allowing
the overall ingestion process to continue without crashing.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from tree_sitter import Parser
from tree_sitter_languages import get_language

# --- Configuration ---
# Set up a dedicated logger for the parser. This allows us to capture parsing
# errors without polluting the main application's output.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
parser_logger = logging.getLogger(__name__)

# Initialize the Tree-sitter parser with the Python language grammar.
# This is a one-time setup that can be reused for parsing multiple files.
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

def _create_unique_id(file_path_str: str, parts: List[str]) -> str:
    """Creates a standardized unique identifier for a code entity."""
    return f"{file_path_str}::{'::'.join(parts)}"

# --- Core Parsing Logic ---

def parse_file_to_graph_components(file_path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Performs a deep, fault-tolerant parse of a single Python file.

    Args:
        file_path: The Path object for the Python file to parse.

    Returns:
        A tuple containing two lists: one for node dictionaries and one for
        edge dictionaries found in the file. Returns empty lists if parsing fails.
    """
    if PARSER is None:
        parser_logger.error("Tree-sitter parser is not initialized. Cannot parse file.")
        return [], []
        
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    file_path_str = file_path.as_posix() # Use POSIX paths for consistency

    try:
        with open(file_path, "rb") as f:
            code_bytes = f.read()
        
        tree = PARSER.parse(code_bytes)
        root_node = tree.root_node

        # Handle syntax errors gracefully
        if root_node.has_error:
            parser_logger.warning(f"Syntax error in file, skipping: {file_path_str}")
            # Optionally, find the error node and log more details
            error_node = next((child for child in root_node.children if child.type == 'ERROR'), None)
            if error_node:
                line = error_node.start_point[0]
                col = error_node.start_point[1]
                parser_logger.warning(f"  - Error near line {line+1}, column {col+1}")
            return [], []

        # --- Node Extraction ---
        file_id = file_path_str
        nodes.append({
            "id": file_id, "type": "File", "name": file_path.name,
            "file_path": file_path_str,
            "start_line": 0, "end_line": len(code_bytes.decode('utf8', 'ignore').splitlines())
        })

        # Using tree-sitter queries for robust and precise extraction
        # Query for classes and top-level functions
        class_query = PYTHON_LANGUAGE.query("(class_definition name: (identifier) @class.name) @class.body")
        func_query = PYTHON_LANGUAGE.query("(function_definition name: (identifier) @func.name) @func.body")
        
        # Query for imports
        import_query_str = """
        (import_statement name: (dotted_name) @import.name)
        (import_from_statement module_name: (dotted_name) @import.from name: (dotted_name) @import.name)
        """
        import_query = PYTHON_LANGUAGE.query(import_query_str)

        captures = class_query.captures(root_node) + func_query.captures(root_node)
        
        for node, capture_name in captures:
            if capture_name == "class.name":
                class_name = _get_node_text(node, code_bytes)
                class_id = _create_unique_id(file_path_str, [class_name])
                
                nodes.append({
                    "id": class_id, "type": "Class", "name": class_name,
                    "file_path": file_path_str,
                    "start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1
                })
                edges.append({"source": file_id, "target": class_id, "type": "DEFINES"})
                
                # Find methods within this class
                method_captures = func_query.captures(node.parent) # Search within the class_definition node
                for method_node, method_capture_name in method_captures:
                    if method_capture_name == "func.name":
                        method_name = _get_node_text(method_node, code_bytes)
                        method_id = _create_unique_id(file_path_str, [class_name, method_name])
                        nodes.append({
                            "id": method_id, "type": "Method", "name": method_name,
                            "file_path": file_path_str,
                            "start_line": method_node.start_point[0] + 1, "end_line": method_node.end_point[0] + 1
                        })
                        edges.append({"source": class_id, "target": method_id, "type": "DEFINES"})
            
            elif capture_name == "func.name":
                 # Ensure it's a top-level function, not a method
                is_method = any(p.type == 'class_definition' for p in _get_node_ancestors(node))
                if not is_method:
                    func_name = _get_node_text(node, code_bytes)
                    func_id = _create_unique_id(file_path_str, [func_name])
                    nodes.append({
                        "id": func_id, "type": "Function", "name": func_name,
                        "file_path": file_path_str,
                        "start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1
                    })
                    edges.append({"source": file_id, "target": func_id, "type": "DEFINES"})

        # --- Edge Extraction (Imports and Calls) ---
        import_captures = import_query.captures(root_node)
        for node, _ in import_captures:
            import_name = _get_node_text(node, code_bytes)
            import_id = f"import::{import_name}" # A unique prefix for external modules
            
            # Add a node for the imported entity if it doesn't exist
            if not any(n['id'] == import_id for n in nodes):
                 nodes.append({
                    "id": import_id, "type": "Import", "name": import_name,
                    "file_path": "external", "start_line": 0, "end_line": 0
                })
            edges.append({"source": file_id, "target": import_id, "type": "IMPORTS"})
            
        # Call extraction is more complex and will be added in a future iteration
        # For now, we focus on the structural definitions and imports.

    except FileNotFoundError:
        parser_logger.error(f"File not found: {file_path_str}")
        return [], []
    except Exception as e:
        parser_logger.error(f"An unexpected error occurred while parsing {file_path_str}: {e}")
        return [], []

    return nodes, edges

def _get_node_ancestors(node):
    """Helper to walk up the tree from a given node."""
    curr = node.parent
    while curr:
        yield curr
        curr = curr.parent
