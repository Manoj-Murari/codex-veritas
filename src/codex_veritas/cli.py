# src/codex_veritas/cli.py

"""
Command-Line Interface for the Codex Veritas project.

This module provides a user-friendly command-line interface (CLI) using the Typer
library. It exposes high-level commands to interact with the analysis pipeline,
making it easy to run complex processes like code graph generation and semantic
embedding from the terminal.

Current Commands:
- analyze: Runs the full analysis pipeline (AST parsing and semantic embedding).
- start: Launches the web UI.
"""

import typer
from pathlib import Path

# --- Local Imports ---
# These imports bring in the core logic from our other modules.
from codex_veritas.analysis import ast_parser
from codex_veritas.analysis import semantic_layer
from codex_veritas.app import main as app_main

# --- CLI Application Initialization ---
# This creates the main 'codex' command.
app = typer.Typer(
    name="codex",
    help="Codex Veritas: An AI software engineering platform for structural honesty.",
    add_completion=False,
)

# --- CLI Commands ---

@app.command()
def analyze(
    repo_path: Path = typer.Option("target_repo", help="Path to the repository to analyze."),
    output_file: Path = typer.Option("output/code_graph.json", help="Where to save the code graph."),
    db_path: Path = typer.Option("code_db", help="Path to store the ChromaDB database."),
    collection_name: str = typer.Option("code_embeddings", help="Name of the ChromaDB collection."),
):
    """
    Runs the full analysis pipeline on the given repository.

    Tier 1: AST-based structural code graph.
    Tier 2: Semantic embeddings in a vector database.
    """
    typer.secho("🚀 Starting full codebase analysis...", fg=typer.colors.CYAN)

    # Run Tier 1: AST Parsing
    typer.echo("\n--- Running Tier 1: Building Structural Code Graph ---")
    ast_parser.build_code_graph(repo_path, output_file)
    typer.secho("✅ Tier 1 Complete.", fg=typer.colors.GREEN)

    # Run Tier 2: Semantic Layer
    typer.echo("\n--- Running Tier 2: Building Semantic Layer ---")
    # --- FINAL FIX HERE: Changed create_semantic_layer to the correct function name ---
    semantic_layer.build_semantic_layer(output_file, repo_path, db_path, collection_name)
    typer.secho("✅ Tier 2 Complete.", fg=typer.colors.GREEN)

    typer.secho("\n🎉 Full analysis complete! The AI agent is now ready.", fg=typer.colors.BRIGHT_GREEN)

@app.command()
def start():
    """
    Starts the web server to launch the chat UI.
    """
    typer.secho("🚀 Starting the Codex Veritas web application...", fg=typer.colors.CYAN)
    typer.echo("Visit http://127.0.0.1:5001 in your browser.")
    app_main.run()

# --- Main Execution Guard ---
# This ensures the app runs when the script is executed directly.
if __name__ == "__main__":
    app()

