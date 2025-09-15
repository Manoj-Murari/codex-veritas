"""
The Agent's Command Center.

This module provides the primary command-line interface (CLI) to dispatch the
Codex Veritas agent on autonomous missions.
"""

from typing_extensions import Annotated
import typer
from rich.console import Console
from rich.panel import Panel

# --- Local Imports ---
# The main CLI now delegates all logic to the mission control orchestrator.
from ..mission_control import execute_mission, create_new_feature_from_issue

# --- CLI Application Initialization ---
app = typer.Typer(
    name="agent",
    help="Codex Veritas: Dispatches an AI agent for autonomous software engineering missions.",
    add_completion=False,
    rich_markup_mode="markdown"
)

console = Console()

# --- Primary CLI Commands ---

@app.command(
    name="run-mission",
    help="Launch a refactoring/debugging mission from a GitHub issue."
)
def run_mission(
    issue_url: Annotated[str, typer.Argument(
        help="The full URL of the GitHub issue that defines the agent's mission."
    )],
):
    """
    Primary entry point for refactoring and general tasks.

    It takes a GitHub issue URL, hands it off to the mission control
    orchestrator, and lets the autonomous loop handle the rest.
    """
    try:
        # This defaults to the 'refactor' persona in mission_control
        execute_mission(issue_url)
    except Exception as e:
        console.print(Panel(
            f"[bold red]A fatal error occurred during the mission:[/bold red]\n\n{e}",
            title="[bold red]Mission Failure[/bold red]",
            border_style="red"
        ))
        raise typer.Exit(code=1)

@app.command(
    name="create-feature",
    help="Launch a feature development mission from a GitHub issue."
)
def create_feature(
    issue_url: Annotated[str, typer.Argument(
        help="The full URL of the GitHub issue that describes the new feature."
    )],
):
    """
    Entry point for creating new features.

    This command uses a specialized 'feature_dev' persona to guide the agent.
    """
    try:
        create_new_feature_from_issue(issue_url)
    except Exception as e:
        console.print(Panel(
            f"[bold red]A fatal error occurred during the feature creation mission:[/bold red]\n\n{e}",
            title="[bold red]Mission Failure[/bold red]",
            border_style="red"
        ))
        raise typer.Exit(code=1)


# --- Main Execution Guard ---
if __name__ == "__main__":
    app()

