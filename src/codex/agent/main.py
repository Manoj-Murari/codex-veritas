"""
The Agent's Command Center.

This module provides a command-line interface (CLI) to interact with the
Codex Veritas agent. It allows a user to assign a high-level task to the
agent and observe its execution in real-time.

The script is responsible for:
1.  Setting up all necessary dependencies, including the `CodeGraph` and the
    `QueryEngine`.
2.  Initializing the `Agent` with these services.
3.  Providing a simple Typer command to pass a task string to the agent's
    `run` method.
4.  Printing the final result from the agent to the console.
"""

from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

# --- Local Imports ---
from ..graph.core import CodeGraph
from ..query.engine import QueryEngine
from .core import Agent

# --- CLI Application Initialization ---
app = typer.Typer(
    name="agent",
    help="Codex Veritas: An AI agent for software engineering tasks.",
    add_completion=False,
    rich_markup_mode="markdown"
)

console = Console()

# --- A "Dummy" Engine for Simple, Non-Code-Aware Tasks ---
class DummyQueryEngine:
    """A placeholder query engine for when no analysis files are provided."""
    
    def query_semantic(self, query_text: str) -> str:
        """(Disabled) Performs a semantic search for code."""
        return "Error: Cannot perform semantic query. No semantic database was provided."
    
    def _query_structural(self, node_name: str, relations: str) -> str:
        """(Disabled) Queries the code graph for relationships."""
        return "Error: Cannot perform structural query. No code graph was provided."

# --- CLI Command ---
@app.command(
    help="Run the agent with a specific task."
)
def run(
    task: Annotated[str, typer.Argument(help="The high-level task for the agent to perform.")],
    
    graph_path: Annotated[Optional[Path], typer.Option(
        "--graph", "-g",
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="[Optional] Path to the code_graph.json file for code-aware tasks."
    )] = None,
    
    db_path: Annotated[Optional[Path], typer.Option(
        "--db", "-d",
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="[Optional] Path to the ChromaDB semantic database for code-aware tasks."
    )] = None,
):
    """
    Initializes all services and runs the agent with the provided task.
    """
    console.print(Panel(f"[bold green]🚀 Initializing Agent for Task:[/bold green] [italic]{task}[/italic]"))

    query_engine: QueryEngine | DummyQueryEngine

    if graph_path and db_path:
        if not graph_path.exists():
            console.print(f"[bold red]Error:[/bold red] Code graph not found at: {graph_path}")
            raise typer.Exit(code=1)
        if not db_path.exists():
            console.print(f"[bold red]Error:[/bold red] Semantic database not found at: {db_path}")
            raise typer.Exit(code=1)
            
        console.print("   - Loading code graph for code-aware tasks...")
        graph = CodeGraph()
        graph.load_from_json(graph_path)

        console.print("   - Initializing full query engine...")
        query_engine = QueryEngine(db_path=db_path, graph=graph)
    else:
        console.print("   - No analysis files provided. Initializing in simple mode.")
        query_engine = DummyQueryEngine()

    console.print("   - Booting agent brain...")
    agent = Agent(query_engine)

    console.print(Panel("[bold green]🤖 Agent execution started...[/bold green]"))
    
    final_answer = agent.run(task)
    
    console.print(Panel(f"[bold green]✅ Final Answer Received[/bold green]"))
    console.print(final_answer)

if __name__ == "__main__":
    app()