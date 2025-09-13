# tests/test_graph.py

"""
Unit Tests for the CodeGraph Data Model.

This test suite verifies the functionality of the `CodeGraph` class, ensuring
that nodes and edges are added correctly, queries (get_callers, get_callees)
return the expected results, and serialization/deserialization processes
work reliably.

These tests are crucial for maintaining the integrity of our core data model
as the project evolves.
"""

import pytest
from pathlib import Path

# --- Local Imports from the `codex` package ---
# Note: Poetry's test runner will handle the path correctly.
from src.codex.graph.core import CodeGraph

# --- Test Fixtures ---
# Fixtures provide a consistent, reusable setup for tests.

@pytest.fixture
def empty_graph() -> CodeGraph:
    """Returns a new, empty CodeGraph instance for each test."""
    return CodeGraph()

@pytest.fixture
def sample_graph() -> CodeGraph:
    """Returns a pre-populated CodeGraph for testing query methods."""
    graph = CodeGraph()
    nodes = [
        {"id": "file.py::func_a", "type": "Function", "name": "func_a"},
        {"id": "file.py::func_b", "type": "Function", "name": "func_b"},
        {"id": "file.py::main", "type": "Function", "name": "main"},
    ]
    edges = [
        {"source": "file.py::main", "target": "file.py::func_a", "type": "CALLS"},
        {"source": "file.py::main", "target": "file.py::func_b", "type": "CALLS"},
        {"source": "file.py::func_a", "target": "file.py::func_b", "type": "CALLS"},
    ]
    graph.merge_components(nodes, edges)
    return graph

# --- Test Cases ---

def test_add_node(empty_graph: CodeGraph):
    """Verify that a single node can be added with attributes."""
    empty_graph.add_node("node1", type="Function", name="my_func")
    assert "node1" in empty_graph.graph
    assert empty_graph.graph.nodes["node1"]["type"] == "Function"
    assert empty_graph.graph.nodes["node1"]["name"] == "my_func"
    assert len(empty_graph.graph.nodes) == 1

def test_add_edge(empty_graph: CodeGraph):
    """Verify that an edge can be added between two existing nodes."""
    empty_graph.add_node("caller", type="Function")
    empty_graph.add_node("callee", type="Function")
    empty_graph.add_edge("caller", "callee", type="CALLS")
    
    assert empty_graph.graph.has_edge("caller", "callee")
    assert len(empty_graph.graph.edges) == 1

def test_add_edge_raises_error_for_missing_node(empty_graph: CodeGraph):
    """Verify that adding an edge to a non-existent node raises a ValueError."""
    empty_graph.add_node("source_node")
    with pytest.raises(ValueError, match="Target node 'missing_node' not found"):
        empty_graph.add_edge("source_node", "missing_node")

def test_merge_components(empty_graph: CodeGraph):
    """Test the merging of nodes and edges from a parser's output."""
    nodes = [{"id": "n1", "type": "File"}, {"id": "n2", "type": "Function"}]
    edges = [{"source": "n1", "target": "n2", "type": "DEFINES"}]
    empty_graph.merge_components(nodes, edges)

    assert len(empty_graph.graph.nodes) == 2
    assert len(empty_graph.graph.edges) == 1
    assert empty_graph.graph.has_edge("n1", "n2")

def test_get_callers(sample_graph: CodeGraph):
    """Test retrieving the callers of a specific function."""
    callers_of_b = sample_graph.get_callers("file.py::func_b")
    caller_ids = {c['id'] for c in callers_of_b}
    
    assert len(callers_of_b) == 2
    assert "file.py::main" in caller_ids
    assert "file.py::func_a" in caller_ids

def test_get_callees(sample_graph: CodeGraph):
    """Test retrieving the functions called by a specific function."""
    callees_of_main = sample_graph.get_callees("file.py::main")
    callee_ids = {c['id'] for c in callees_of_main}

    assert len(callees_of_main) == 2
    assert "file.py::func_a" in callee_ids
    assert "file.py::func_b" in callee_ids

def test_get_callers_for_node_with_no_callers(sample_graph: CodeGraph):
    """Test that get_callers returns an empty list for a node with no incoming calls."""
    callers = sample_graph.get_callers("file.py::main")
    assert callers == []

def test_serialization_deserialization(sample_graph: CodeGraph, tmp_path: Path):
    """
    Verify that a graph can be saved to and loaded from a JSON file
    without losing its structure. `tmp_path` is a pytest fixture for a temporary directory.
    """
    file_path = tmp_path / "test_graph.json"
    
    # Save the graph
    sample_graph.serialize_to_json(file_path)
    assert file_path.exists()
    
    # Load into a new graph instance
    new_graph = CodeGraph()
    new_graph.load_from_json(file_path)
    
    # Verify the new graph is identical
    assert len(new_graph.graph.nodes) == len(sample_graph.graph.nodes)
    assert len(new_graph.graph.edges) == len(sample_graph.graph.edges)
    assert new_graph.graph.has_edge("file.py::main", "file.py::func_a")
