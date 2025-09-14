"""
The Unified Query Engine: The Central Dispatch for Insights.

This module provides a centralized, high-level API for querying the different
layers of our codebase analysis. It acts as an abstraction layer, separating the
caller (e.g., a CLI or an AI agent) from the underlying data sources.

The `QueryEngine` class wraps the structural and semantic query functions,
providing a stateful object that can be initialized with paths to the necessary
data files (the code graph and the vector database).
"""

from pathlib import Path
from typing import List, Dict, Any

import chromadb
from chromadb.utils import embedding_functions
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# --- Local Imports from the `codex` package ---
from ..graph.core import CodeGraph

# --- Configuration ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_COLLECTION_NAME = "codex_semantic_index"

class QueryEngine:
    """A centralized engine for querying structural and semantic data."""

    def __init__(self, db_path: Path, graph_path: Path = None):
        """
        Initializes the QueryEngine.

        Args:
            db_path: Path to the ChromaDB database directory.
            graph_path: Optional path to the code_graph.json file.
        """
        self.db_path = db_path
        self.graph_path = graph_path
        self.graph = None
        self.console = Console()

        if self.graph_path and self.graph_path.exists():
            self.graph = CodeGraph()
            self.graph.load_from_json(self.graph_path)

        # Initialize ChromaDB client and collection
        if not db_path.exists():
            raise FileNotFoundError(f"Semantic database not found at {db_path}")
        
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        client = chromadb.PersistentClient(path=str(db_path))
        self.collection = client.get_collection(
            name=DEFAULT_COLLECTION_NAME,
            embedding_function=sentence_transformer_ef
        )

    def query_semantic(self, query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Performs a semantic similarity search."""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["metadatas", "documents", "distances"]
        )
        
        ids = results.get('ids', [[]])[0]
        distances = results.get('distances', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        documents = results.get('documents', [[]])[0]

        return [
            {"id": _id, "distance": dist, "metadata": meta, "document": doc}
            for _id, dist, meta, doc in zip(ids, distances, metadatas, documents)
        ]

    def _query_structural(self, node_name: str, relations: str) -> List[Dict[str, Any]]:
        """Internal helper for structural queries."""
        if not self.graph:
            return []
            
        target_node_id = next((node_id for node_id, data in self.graph.graph.nodes(data=True) if data.get('name') == node_name), None)
        
        if not target_node_id:
            return []

        if relations == 'callers':
            return self.graph.get_callers(target_node_id)
        elif relations == 'callees':
            return self.graph.get_callees(target_node_id)
        
        return []

    def display_semantic_results(self, results: List[Dict[str, Any]]):
        """Displays semantic search results in a formatted panel."""
        self.console.print(Panel("[bold cyan]Semantic Search Results[/bold cyan]"))
        if not results:
            self.console.print("No semantic results found.")
            return

        for i, res in enumerate(results):
            meta = res.get("metadata", {})
            title = f"Rank {i+1} | Distance: {res.get('distance', 0):.2f} | {meta.get('name', 'N/A')}"
            
            # Use Rich's Syntax for beautiful code highlighting
            syntax = Syntax(res.get("document", ""), "python", theme="monokai", line_numbers=True)
            panel = Panel(
                syntax,
                title=title,
                border_style="blue",
                subtitle=f"[dim]{meta.get('file_path', 'N/A')}[/dim]",
                subtitle_align="right"
            )
            self.console.print(panel)

    def _display_structural_table(self, title: str, results: List[Dict[str, Any]]):
        """Displays structural query results in a formatted table."""
        if not results:
            self.console.print(Panel(f"No results found for '[italic]{title}[/italic]'."))
            return

        table = Table(title=title)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("File Path", style="green")
        table.add_column("Lines", justify="right", style="yellow")

        for node in results:
            name = node.get("name", "N/A")
            node_type = node.get("type", "N/A")
            file_path = node.get("file_path", "N/A")
            lines = f"{node.get('start_line', '?')}-{node.get('end_line', '?')}"
            table.add_row(name, node_type, file_path, lines)
        
        self.console.print(table)

    def explain_concept(self, query_text: str):
        """Orchestrates the hybrid semantic + structural explanation."""
        self.console.print("\n[bold]Step 1: Finding semantically relevant code...[/bold]")
        semantic_results = self.query_semantic(query_text, n_results=1)
        
        if not semantic_results:
            self.console.print("Could not find any semantically relevant code to begin explanation.")
            return

        self.display_semantic_results(semantic_results)
        
        top_result = semantic_results[0]
        top_node_name = top_result.get("metadata", {}).get("name")

        if not top_node_name or not self.graph:
            return

        self.console.print("\n[bold]Step 2: Expanding with structural context...[/bold]")
        callers = self._query_structural(top_node_name, "callers")
        self._display_structural_table(f"Who calls '{top_node_name}'?", callers)
        
        callees = self._query_structural(top_node_name, "callees")
        self._display_structural_table(f"What does '{top_node_name}' call?", callees)

