"""
The Hybrid Command-Line Interface (CLI).

This module serves as the primary user-facing entry point for all of Codex
Veritas's analysis and reporting capabilities. It uses Typer to provide a clean,
discoverable, and powerful set of commands.

This single tool orchestrates the entire workflow:
1. `ingest`: (From Sprint 1) Parses a repository into a structural code graph.
2. `index`: (From Sprint 2) Builds a semantic vector database from the graph.
3. `query`: (From Sprint 2) Runs structural, semantic, or hybrid queries.
4. `report`: (From Sprint 3) Generates a high-level Markdown codebase guide.
"""

from pathlib import Path
from typing_extensions import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

# --- Local Imports from the `codex` package ---
from ..graph.core import CodeGraph
from ..query.engine import QueryEngine
from ..semantic.indexer import build_semantic_layer
from ..report.generator import generate_report

# --- CLI Application Initialization ---
app = typer.Typer(
    name="codex",
    help="Codex Veritas: A command-line toolkit for code analysis and understanding.",
    add_completion=False,
    rich_markup_mode="markdown"
)

console = Console()

# --- CLI Commands ---

@app.command()
def index(
    graph_path: Annotated[Path, typer.Option(
        "--graph", "-g",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the code_graph.json file."
    )] = Path("code_graph.json"),
    repo_path: Annotated[Path, typer.Option(
        "--repo", "-r",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to the source repository (for reading file contents)."
    )] = Path("target_repo"),
    db_path: Annotated[Path, typer.Option(
        "--db", "-d",
        writable=True,
        resolve_path=True,
        help="Path to store the ChromaDB semantic database."
    )] = Path("semantic_db")
):
    """
    Builds the Semantic Layer (Vector Database) from an existing Code Graph.
    """
    console.print(Panel("[bold green]🧠 Building Semantic Layer[/bold green]"))
    build_semantic_layer(
        graph_path=graph_path,
        repo_path=repo_path,
        db_path=db_path,
        collection_name="codex_semantic_index" # Standardized name
    )
    console.print(Panel("[bold green]🎉 Semantic Layer Build Complete[/bold green]"))


@app.command()
def semantic(
    query_text: Annotated[str, typer.Argument(help="The natural language query to search for.")],
    db_path: Annotated[Path, typer.Option(
        "--db", "-d",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to the ChromaDB semantic database."
    )] = Path("semantic_db")
):
    """
    Performs a semantic search for code related to the QUERY_TEXT.
    """
    console.print(f"🧠 Performing semantic search for '[italic]{query_text}[/italic]'...")
    engine = QueryEngine(db_path=db_path)
    results = engine.query_semantic(query_text)
    engine.display_semantic_results(results)

@app.command()
def explain(
    query_text: Annotated[str, typer.Argument(help="The concept or entity to explain.")],
    graph_path: Annotated[Path, typer.Option(
        "--graph", "-g",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the code_graph.json file."
    )] = Path("code_graph.json"),
    db_path: Annotated[Path, typer.Option(
        "--db", "-d",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to the ChromaDB semantic database."
    )] = Path("semantic_db")
):
    """
    Provides a hybrid (semantic + structural) explanation for a given concept.
    """
    console.print(Panel(f"[bold green]🕵️ Starting Hybrid Explanation for: '[italic]{query_text}[/italic]'[/bold green]"))
    engine = QueryEngine(db_path=db_path, graph_path=graph_path)
    engine.explain_concept(query_text)
    console.print(Panel("[bold green]✅ Hybrid explanation complete.[/bold green]"))


@app.command()
def report(
    graph_path: Annotated[Path, typer.Option(
        "--graph", "-g",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the code_graph.json file to generate the report from."
    )] = Path("code_graph.json"),
    output_file: Annotated[Path, typer.Option(
        "--output", "-o",
        writable=True,
        resolve_path=True,
        help="Path to save the generated Markdown report."
    )] = Path("codebase_guide.md")
):
    """
    Generates a high-level Markdown "Codebase Guide" from a Code Graph.
    """
    console.print(Panel("[bold green]📄 Generating Codebase Guide...[/bold green]"))
    
    graph = CodeGraph()
    console.print(f"   - Loading graph from [cyan]{graph_path}[/cyan]...")
    graph.load_from_json(graph_path)
    
    console.print("   - Analyzing components and compiling report...")
    report_content = generate_report(graph)
    
    try:
        output_file.write_text(report_content, encoding="utf-8")
        console.print(f"   - Report saved successfully to [cyan]{output_file}[/cyan].")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to save report file: {e}")
        raise typer.Exit(code=1)
        
    console.print(Panel("[bold green]✅ Report generation complete![/bold green]"))


# --- Main Execution Guard ---
if __name__ == "__main__":
    app()

