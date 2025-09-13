# src/codex/graph/core.py

"""
Core Data Model for the Code Graph.

This module defines the `CodeGraph` class, which serves as the central,
in-memory representation of a repository's structure. It is built upon the
powerful `networkx` library to provide a robust and queryable graph structure.

The class is responsible for aggregating nodes (code entities) and edges
(relationships) from individual file parses into a single, cohesive graph.
It also provides methods for querying this graph (e.g., finding callers/callees)
and for serializing the entire structure to and from a JSON format.
"""

import json
from pathlib import Path
from typing import List, Dict, Any

import networkx as nx
from networkx.readwrite import json_graph

class CodeGraph:
    """An in-memory representation of the repository's structural code graph."""

    def __init__(self):
        """Initializes an empty `networkx.DiGraph`."""
        self.graph = nx.DiGraph()

    def add_node(self, node_id: str, **attributes: Any):
        """
        Adds a single node to the graph with its associated metadata.

        Args:
            node_id: The unique identifier for the node.
            **attributes: Keyword arguments for node metadata (e.g., type, name).
        """
        self.graph.add_node(node_id, **attributes)

    def add_edge(self, source_id: str, target_id: str, **attributes: Any):
        """
        Adds a directed edge between two nodes.

        Args:
            source_id: The ID of the source node.
            target_id: The ID of the target node.
            **attributes: Keyword arguments for edge metadata (e.g., type).
        
        Raises:
            ValueError: If the source or target node does not exist in the graph.
        """
        if not self.graph.has_node(source_id):
            raise ValueError(f"Source node '{source_id}' not found in graph.")
        if not self.graph.has_node(target_id):
            raise ValueError(f"Target node '{target_id}' not found in graph.")
        self.graph.add_edge(source_id, target_id, **attributes)

    def merge_components(self, nodes: List[Dict], edges: List[Dict]):
        """
        Adds a list of nodes and edges (from a single file parse) into the main graph.

        Args:
            nodes: A list of node dictionaries, each with an 'id' key.
            edges: A list of edge dictionaries, each with 'source' and 'target' keys.
        """
        for node_data in nodes:
            node_id = node_data.pop("id")
            self.add_node(node_id, **node_data)
        
        for edge_data in edges:
            source = edge_data.pop("source")
            target = edge_data.pop("target")
            self.add_edge(source, target, **edge_data)

    def get_callers(self, node_id: str) -> List[Dict]:
        """
        Returns a list of nodes that have a 'CALLS' edge pointing to the given node_id.

        Args:
            node_id: The unique ID of the function/method node.

        Returns:
            A list of node dictionaries representing the callers.
        """
        if not self.graph.has_node(node_id):
            return []
        
        caller_ids = list(self.graph.predecessors(node_id))
        
        return [
            {"id": caller_id, **self.graph.nodes[caller_id]}
            for caller_id in caller_ids
        ]

    def get_callees(self, node_id: str) -> List[Dict]:
        """
        Returns a list of nodes that the given node_id has a 'CALLS' edge pointing to.

        Args:
            node_id: The unique ID of the function/method node.

        Returns:
            A list of node dictionaries representing the callees.
        """
        if not self.graph.has_node(node_id):
            return []
            
        callee_ids = list(self.graph.successors(node_id))

        return [
            {"id": callee_id, **self.graph.nodes[callee_id]}
            for callee_id in callee_ids
        ]

    def serialize_to_json(self, file_path: Path):
        """
        Saves the graph to a JSON file in a node-link format.

        Args:
            file_path: The Path object where the JSON file will be saved.
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # --- FIXED HERE: Explicitly set `edges` to silence the FutureWarning ---
        data = json_graph.node_link_data(self.graph, edges="links")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def load_from_json(self, file_path: Path):
        """
        Loads a graph from a JSON file in a node-link format.

        Args:
            file_path: The Path object of the JSON file to load.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # --- FIXED HERE: Explicitly set `edges` to silence the FutureWarning ---
        self.graph = json_graph.node_link_graph(data, edges="links")

