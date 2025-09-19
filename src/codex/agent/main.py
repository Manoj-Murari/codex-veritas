"""
The Agent's Command Center.

This module provides a command-line interface (CLI) to orchestrate and
launch the Codex Veritas agent on various autonomous missions.
"""
from pathlib import Path
from typing_extensions import Annotated
import typer
from rich.console import Console
from rich.panel import Panel

# --- Local Imports ---
from ..mission_control import (
    execute_mission,
    create_new_feature_from_issue,
    execute_fix_bug_mission, # --- NEW: Import the dedicated bug-fixing orchestrator ---
)

# --- CLI Application Initialization ---
app = typer.Typer(
    name="agent",
    help="Codex Veritas: An AI agent for software engineering tasks.",
    add_completion=False,
    rich_markup_mode="markdown"
)

console = Console()

# --- CLI Commands ---

@app.command(
    name="run-mission",
    help="Run a general-purpose mission from a GitHub issue."
)
def run_mission_command(
    issue_url: Annotated[str, typer.Argument(help="The full URL of the GitHub issue.")],
):
    """
    A CLI wrapper that executes a mission based on a GitHub issue.
    """
    execute_mission(issue_url=issue_url, persona="default")

@app.command(
    name="create-feature",
    help="Create a new feature based on a GitHub issue."
)
def create_feature_command(
    issue_url: Annotated[str, typer.Argument(help="The full URL of the GitHub issue for the new feature.")],
):
    """
    A CLI wrapper for the 'feature_dev' persona.
    """
    create_new_feature_from_issue(issue_url=issue_url)


# --- CORRECTED: The fix-bug command is now a simple wrapper ---
@app.command(
    name="fix-bug",
    help="Launch the TDD agent to write a test, fix a bug, and verify."
)
def fix_bug_command():
    """
    A simple CLI wrapper that calls the dedicated TDD mission orchestrator.
    """
    # All complex setup logic is now handled in mission_control.py
    execute_fix_bug_mission()


if __name__ == "__main__":
    app()

