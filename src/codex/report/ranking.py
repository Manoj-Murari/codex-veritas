"""
Graph Ranking and Analysis Module.

This module provides functions for analyzing the CodeGraph to extract high-level
insights and identify key architectural components. It leverages the power of
the `networkx` library to apply graph theory algorithms.

The primary function, `rank_nodes_by_centrality`, uses the PageRank algorithm
(analogous to how Google first ranked web pages) to determine the "importance"
or "centrality" of each function and class in the codebase. Nodes with many
incoming connections (i.e., functions that are called frequently by many other
parts of the code) will receive a higher rank.

This ranking is a cornerstone of our automated reporting, as it allows us to
programmatically identify the most critical parts of an architecture to highlight
for the user.
"""

from typing import List, Dict, Any
import networkx as nx # --- FIXED HERE: Import networkx directly ---

from ..graph.core import CodeGraph

def rank_nodes_by_centrality(graph: CodeGraph, top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Ranks nodes in the CodeGraph by their PageRank centrality.

    This function identifies the most important/central nodes in the graph,
    which typically correspond to key architectural components like utility
    functions, core classes, or request handlers.

    Args:
        graph: The CodeGraph instance to analyze.
        top_n: The number of top-ranked nodes to return.

    Returns:
        A list of node dictionaries, sorted by their centrality score in
        descending order. Each dictionary includes the node's attributes
        plus its calculated rank.
    """
    if not graph.graph or not graph.graph.nodes:
        return []

    # --- FIXED HERE: Call the official networkx.pagerank function directly
    # on the underlying graph object, instead of a non-existent method. ---
    try:
        # We use a high alpha to prioritize direct connections heavily.
        centrality_scores = nx.pagerank(graph.graph, alpha=0.85)
    except Exception:
        # Fallback for empty or disconnected graphs
        return []

    # We are only interested in ranking classes, methods, and functions
    ranked_nodes = []
    for node_id, data in graph.graph.nodes(data=True):
        # --- FIXED HERE: Now this `data.get("type")` will work because the
        # node data is correctly loaded and the algorithm doesn't exit early. ---
        if data.get("type") in ["Class", "Method", "Function"]:
            score = centrality_scores.get(node_id, 0)
            node_info = {
                "id": node_id,
                "rank": score,
                **data
            }
            ranked_nodes.append(node_info)

    # Sort the nodes by their rank in descending order
    ranked_nodes.sort(key=lambda x: x["rank"], reverse=True)

    return ranked_nodes[:top_n]

