# src/codex/ingestion/main.py

"""
The Master Ingestion Script: The Orchestrator.

This module provides the primary command-line interface (CLI) for running the
codebase ingestion process. It uses Typer to offer a clean and user-friendly
interface.

The script orchestrates the entire workflow:
1. Discovering all Python files within a target repository.
2. Initializing a central `CodeGraph` instance.
3. Calling the `ASTParser` for each file to extract its structural components.
4. Merging these components into the main `CodeGraph`.
5. Serializing the final, complete graph to a JSON file for later use.
"""

import time
from pathlib import Path
from typing_extensions import Annotated

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

# --- Local Imports from the `codex` package ---
from ..graph.core import CodeGraph
from .parser import parse_file_to_graph_components

# --- CLI Application Initialization ---
app = typer.Typer(
    name="ingest",
    help="Codex Veritas: A command-line tool to parse a repository and create a structural code graph.",
    add_completion=False
)

# --- CLI Command ---

@app.command(
    help="Parse a Python repository and generate a code graph JSON file."
)
def parse(
    repo_path: Annotated[Path, typer.Option(
        "--path", "-p",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="The path to the Python repository to analyze."
    )] = Path.cwd(),
    
    output_file: Annotated[Path, typer.Option(
        "--output", "-o",
        writable=True,
        resolve_path=True,
        help="The path where the output graph JSON file will be saved."
    )] = Path("code_graph.json")
):
    """
    Orchestrates the entire parsing process for a given repository.
    """
    start_time = time.time()
    typer.secho(f"🚀 Starting ingestion process for repository: {repo_path}", fg=typer.colors.CYAN)

    # 1. Discover all .py files
    typer.echo("   - Discovering Python files...")
    python_files = list(repo_path.rglob("*.py"))
    
    # Exclude common virtual environment folders for performance and relevance
    python_files = [
        f for f in python_files 
        if '.venv/' not in f.as_posix() and '/venv/' not in f.as_posix() and '/.git/' not in f.as_posix()
    ]
    
    if not python_files:
        typer.secho("⚠️ No Python files found in the specified directory.", fg=typer.colors.YELLOW)
        raise typer.Exit()
        
    typer.secho(f"   - Found {len(python_files)} Python files to process.", fg=typer.colors.GREEN)

    # 2. Initialize CodeGraph
    main_graph = CodeGraph()

    # 3. & 4. Process each file and merge components
    typer.echo("\n--- 🧠 Parsing files and building graph ---")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("[green]Parsing...", total=len(python_files))
        
        for file_path in python_files:
            relative_path = file_path.relative_to(repo_path)
            progress.update(task, description=f"[cyan]Parsing {relative_path}")
            
            # Call the parser to get components for this single file
            nodes, edges = parse_file_to_graph_components(file_path)
            
            # Merge the results into the main graph
            main_graph.merge_components(nodes, edges)
            
            progress.update(task, advance=1)

    # 5. Serialize the final graph
    typer.echo("\n--- 💾 Serializing complete code graph ---")
    main_graph.serialize_to_json(output_file)
    
    end_time = time.time()
    duration = end_time - start_time
    
    typer.secho(f"\n🎉 Ingestion complete in {duration:.2f} seconds!", fg=typer.colors.BRIGHT_GREEN)
    typer.secho(f"   - Graph saved to: {output_file}", fg=typer.colors.GREEN)
    typer.secho(f"   - Total Nodes: {len(main_graph.graph.nodes)}", fg=typer.colors.GREEN)
    typer.secho(f"   - Total Edges: {len(main_graph.graph.edges)}", fg=typer.colors.GREEN)

# --- Main Execution Guard ---
# This allows the script to be run directly for debugging,
# e.g., `python -m src.codex.ingestion.main ...`
if __name__ == "__main__":
    app()
