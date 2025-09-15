"""
The Unified Query Engine: The Central Dispatch for Insights.

This module provides a centralized, high-level API for querying the different
layers of our codebase analysis. It acts as an abstraction layer, separating the
caller (e.g., a CLI or an AI agent) from the underlying data sources.
"""

from pathlib import Path
from typing import List, Dict, Any, Literal, Optional

import chromadb
from chromadb.utils import embedding_functions
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# --- Local Imports ---
from ..graph.core import CodeGraph

# --- Configuration ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_COLLECTION_NAME = "codex_semantic_index"

class QueryEngine:
    """A class to handle both structural and semantic queries of the codebase."""

    def __init__(self, db_path: Path, graph_path: Optional[Path] = None, graph: Optional[CodeGraph] = None):
        """
        Initializes the QueryEngine.

        Args:
            db_path: The path to the ChromaDB database directory.
            graph_path: The Path object for the code_graph.json file.
            graph: An optional, pre-loaded CodeGraph object.
        """
        self.console = Console()
        
        # --- Semantic Setup ---
        if not db_path.exists():
            raise FileNotFoundError(f"Semantic database not found at {db_path}")
        self.db_path = db_path
        self.collection_name = DEFAULT_COLLECTION_NAME
        
        # --- Structural Setup ---
        self.graph = graph
        if self.graph is None and graph_path:
            if not graph_path.exists():
                raise FileNotFoundError(f"Code graph not found at {graph_path}")
            self.graph = CodeGraph()
            self.graph.load_from_json(graph_path)

    def query_semantic(self, query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Performs a semantic similarity search on the vector database."""
        try:
            sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )
            client = chromadb.PersistentClient(path=str(self.db_path))
            collection = client.get_collection(
                name=self.collection_name, 
                embedding_function=sentence_transformer_ef
            )
            results = collection.query(
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
        except Exception as e:
            self.console.print(f"[bold red]Error during semantic query:[/bold red] {e}")
            return []

    def _query_structural(self, node_name: str, relations: Literal['callers', 'callees']) -> List[Dict[str, Any]]:
        """Finds direct relationships for a given function/method."""
        if not self.graph:
            return []
        
        target_node = next((data for node_id, data in self.graph.graph.nodes(data=True) if data.get('name') == node_name), None)
        if not target_node:
            return []
        
        node_id = next((node_id for node_id, data in self.graph.graph.nodes(data=True) if data == target_node), None)
        if not node_id: return []

        if relations == 'callers':
            return self.graph.get_callers(node_id)
        elif relations == 'callees':
            return self.graph.get_callees(node_id)
        return []

    def display_semantic_results(self, results: List[Dict[str, Any]]):
        """Displays semantic search results in a formatted panel."""
        self.console.print(Panel("[bold green]Semantic Search Results[/bold green]"))
        if not results:
            self.console.print("No relevant code snippets found.")
            return

        for i, res in enumerate(results):
            meta = res.get("metadata", {})
            title = f"Rank {i+1} | Distance: {res.get('distance', 0):.2f} | {meta.get('name', 'N/A')}"
            panel = Panel(
                Syntax(res.get("document", ""), "python", theme="monokai", line_numbers=True),
                title=title,
                border_style="cyan",
                subtitle=meta.get('file_path', 'N/A')
            )
            self.console.print(panel)

    def _display_structural_table(self, title: str, nodes: List[Dict[str, Any]]):
        """Displays a list of nodes in a rich table."""
        if not nodes:
            self.console.print(Panel(f"No results found for '[italic]{title}[/italic]'."))
            return
            
        table = Table(title=title)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("File Path", style="green")
        table.add_column("Lines", justify="right", style="yellow")

        for node in nodes:
            name = node.get("name", "N/A")
            node_type = node.get("type", "N/A")
            file_path = node.get("file_path", "N/A")
            lines = f"{node.get('start_line', '?')}-{node.get('end_line', '?')}"
            table.add_row(name, node_type, file_path, lines)
        
        self.console.print(table)

    def explain_concept(self, query_text: str):
        """Provides a hybrid (semantic + structural) explanation for a concept."""
        self.console.print("\n[bold]Step 1: Finding semantically relevant code...[/bold]")
        semantic_results = self.query_semantic(query_text, n_results=1)

        if not semantic_results:
            self.console.print("Could not find any relevant code to start the explanation.")
            return
        
        self.display_semantic_results(semantic_results)
        
        self.console.print("\n[bold]Step 2: Expanding with structural context...[/bold]")
        
        top_result = semantic_results[0]
        node_name = top_result.get("metadata", {}).get("name")

        if not node_name or not self.graph:
            self.console.print("Top semantic result is not a recognized code entity. Cannot perform structural expansion.")
            return

        callers = self._query_structural(node_name, "callers")
        callees = self._query_structural(node_name, "callees")
        
        self._display_structural_table(f"Who calls '{node_name}'?", callers)
        self._display_structural_table(f"What does '{node_name}' call?", callees)

