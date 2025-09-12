# src/codex_veritas/analysis/ast_parser.py

"""
Tier 1: Abstract Syntax Tree (AST) Parser.

This module is responsible for the first layer of code analysis. It walks through a
given source code repository, parses each file into an Abstract Syntax Tree using
the `tree-sitter` library, and extracts key structural information.

The primary output is a "code graph," a JSON file that represents all identified
code objects (classes, functions, methods) as nodes and the relationships between
them (e.g., function calls) as edges. This structural map is the foundation for
all further analysis.
"""

import os
import json
from tree_sitter import Parser
from tree_sitter_languages import get_language
from typing import Dict, List
from pathlib import Path

# --- Helper Functions ---

def get_node_text(node, code_bytes: bytes) -> str:
    """Helper function to get the text of a tree-sitter node."""
    return code_bytes[node.start_byte:node.end_byte].decode('utf8', errors='ignore')

def get_relative_path(file_path: str, repo_root: Path) -> str:
    """Converts an absolute file path to a project-relative path."""
    return os.path.relpath(file_path, repo_root).replace("\\", "/")

# --- Core Parsing Logic ---

def parse_file(file_path: str, lang_name: str, code_bytes: bytes, symbol_table: Dict, repo_root: Path):
    """
    First pass: Identifies all definitions (classes, functions, methods)
    and adds them to the global symbol table.
    """
    language = get_language(lang_name)
    parser = Parser()
    parser.set_language(language)
    tree = parser.parse(code_bytes)
    root_node = tree.root_node
    relative_file_path = get_relative_path(file_path, repo_root)

    nodes = []
    
    class_query = language.query("(class_definition name: (identifier) @class.name)")
    for node, _ in class_query.captures(root_node):
        class_name = get_node_text(node, code_bytes)
        unique_id = f"{relative_file_path}::{class_name}"
        nodes.append({"id": unique_id, "type": "class", "file": relative_file_path, "name": class_name})
        symbol_table[unique_id] = nodes[-1]
        
        method_query = language.query("(function_definition name: (identifier) @method.name)")
        class_body_node = node.parent.child_by_field_name('body')
        if class_body_node:
            for method_node, _ in method_query.captures(class_body_node):
                method_name = get_node_text(method_node, code_bytes)
                method_id = f"{unique_id}::{method_name}"
                nodes.append({"id": method_id, "type": "method", "file": relative_file_path, "name": method_name})
                symbol_table[method_id] = nodes[-1]

    func_query_str = """
        (function_definition name: (identifier) @func.name)
        (#not-inside? @func.name class_definition)
    """
    func_query = language.query(func_query_str)
    for node, _ in func_query.captures(root_node):
        func_name = get_node_text(node, code_bytes)
        unique_id = f"{relative_file_path}::{func_name}"
        nodes.append({"id": unique_id, "type": "function", "file": relative_file_path, "name": func_name})
        symbol_table[unique_id] = nodes[-1]

    return nodes

def resolve_calls(file_path: str, lang_name: str, code_bytes: bytes, symbol_table: Dict, repo_root: Path) -> List[Dict]:
    """

    Second pass: Identifies all calls and resolves them using the symbol table.
    """
    language = get_language(lang_name)
    parser = Parser()
    parser.set_language(language)
    tree = parser.parse(code_bytes)
    root_node = tree.root_node
    
    edges = []
    relative_file_path = get_relative_path(file_path, repo_root)

    call_query_str = """
    (call
        function: [
            (identifier) @call.name
            (attribute attribute: (identifier) @call.name)
        ]
    )
    """
    call_query = language.query(call_query_str)
    for node, _ in call_query.captures(root_node):
        called_name = get_node_text(node, code_bytes)
        
        caller_id = None
        temp_node = node
        while temp_node:
            if temp_node.type == 'function_definition':
                name_node = temp_node.child_by_field_name('name')
                if name_node:
                    caller_name_text = get_node_text(name_node, code_bytes)
                    
                    parent_class_node = None
                    search_node = temp_node.parent
                    while search_node:
                        if search_node.type == 'class_definition':
                            parent_class_node = search_node
                            break
                        search_node = search_node.parent

                    potential_id = ""
                    if parent_class_node:
                        class_name_node = parent_class_node.child_by_field_name('name')
                        if class_name_node:
                            class_name_text = get_node_text(class_name_node, code_bytes)
                            potential_id = f"{relative_file_path}::{class_name_text}::{caller_name_text}"
                    else:
                        potential_id = f"{relative_file_path}::{caller_name_text}"
                    
                    if potential_id in symbol_table:
                        caller_id = potential_id
                        break
            temp_node = temp_node.parent
        
        if not caller_id:
            continue

        target_id = None
        # Heuristic: Find a symbol that ends with the called name.
        # This is a simplification that works well for many codebases.
        for key in symbol_table:
            if key.endswith(f"::{called_name}"):
                target_id = key
                break
        
        if caller_id and target_id:
            edges.append({"source": caller_id, "target": target_id, "type": "CALLS"})

    return edges

# --- Main Execution Function ---
def build_code_graph(repo_path: Path, output_file: Path):
    """Main execution function to build the code graph."""
    print("--- 🔵 Starting Tier 1: Code Graph Construction ---")

    symbol_table = {}
    all_nodes = []
    all_edges = []
    files_to_process = []

    for root, _, files in os.walk(repo_path):
        # Exclude common non-source directories
        if any(skip in root for skip in [".venv", "__pycache__", "tests", "docs", ".git"]):
            continue
        for file in files:
            if file.endswith(".py"):
                files_to_process.append(os.path.join(root, file))

    print(f"\n--- Pass 1: Discovering definitions in {len(files_to_process)} files... ---")
    for file_path in files_to_process:
        try:
            with open(file_path, "rb") as f:
                code_bytes = f.read()
            file_nodes = parse_file(file_path, "python", code_bytes, symbol_table, repo_path)
            all_nodes.extend(file_nodes)
        except Exception as e:
            print(f"  - ❌ Error defining symbols in {get_relative_path(file_path, repo_path)}: {e}")
    print(f"--- ✅ Found {len(symbol_table)} total symbols (classes, methods, functions). ---")

    print(f"\n--- Pass 2: Resolving calls and relationships... ---")
    for file_path in files_to_process:
        try:
            with open(file_path, "rb") as f:
                code_bytes = f.read()
            
            file_edges = resolve_calls(file_path, "python", code_bytes, symbol_table, repo_path)
            all_edges.extend(file_edges)
        except Exception as e:
            print(f"  - ❌ Error resolving calls in {get_relative_path(file_path, repo_path)}: {e}")
    print(f"--- ✅ Resolved {len(all_edges)} total calls. ---")

    full_graph = {"nodes": all_nodes, "edges": all_edges}
    
    # Ensure the output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(full_graph, f, indent=4)

    print(f"\n--- 🎉 Code graph construction complete. ---")
    print(f"  - Found {len(all_nodes)} nodes and {len(all_edges)} edges.")
    print(f"  - Results saved to: {output_file}")

