"""
The Agent's Command Center.

This module provides a command-line interface (CLI) to interact with the
Codex Veritas agent. It allows a user to assign high-level missions to the
agent and observe its autonomous execution.
"""
import shutil
from pathlib import Path
from typing_extensions import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

# --- Local Imports ---
from ..mission_control import execute_mission, create_new_feature_from_issue
from .core import Agent
from .task import Task
from .tools import WORKSPACE_PATH, write_file

# --- CLI Application Initialization ---
app = typer.Typer(
    name="agent",
    help="Codex Veritas: An AI agent for software engineering missions.",
    add_completion=False,
    rich_markup_mode="markdown"
)

console = Console()


@app.command(
    name="run-mission",
    help="[Default] Run a general-purpose mission from a GitHub issue."
)
def run_mission_command(
    issue_url: Annotated[str, typer.Argument(help="The full URL of the GitHub issue defining the mission.")]
):
    """
    A CLI wrapper that executes a mission based on a GitHub issue.
    """
    execute_mission(issue_url=issue_url, persona="default")

@app.command(
    name="create-feature",
    help="Run a feature development mission from a GitHub issue."
)
def create_feature_command(
    issue_url: Annotated[str, typer.Argument(help="The full URL of the GitHub issue defining the new feature.")]
):
    """
    A CLI wrapper that executes a feature creation mission based on a GitHub issue.
    """
    create_new_feature_from_issue(issue_url=issue_url)


# --- NEW: Command for Test Generation (Sprint 15) ---
@app.command(
    name="generate-tests",
    help="Generate a new pytest test file for a given source file."
)
def generate_tests_command(
    file_path: Annotated[Path, typer.Argument(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="The path to the source code file to generate tests for."
    )]
):
    """
    Initializes and runs the agent with a test generation task for a specific file.
    """
    console.print(Panel(f"[bold yellow]🚀 Initializing Test Generation Mission for:[/bold yellow] [italic]{file_path.name}[/italic]"))

    try:
        # 1. Prepare a clean workspace
        if WORKSPACE_PATH.exists():
            shutil.rmtree(WORKSPACE_PATH)
        WORKSPACE_PATH.mkdir()
        console.print(f"  - ✅ Workspace cleaned and prepared at: {WORKSPACE_PATH}")

        # 2. Read the source file and copy it into the workspace
        source_content = file_path.read_text(encoding="utf-8")
        workspace_file_path = file_path.name
        write_file(workspace_file_path, source_content)
        console.print(f"  - ✅ Copied source file to workspace: {workspace_file_path}")

    except Exception as e:
        console.print(f"[bold red]Error during workspace setup:[/bold red] {e}")
        raise typer.Exit(code=1)

    # 3. Formulate the mission and initialize the agent
    mission = (
        f"Your goal is to generate a complete pytest test file for the code in `{workspace_file_path}`. "
        "You must use the 'tester' persona and follow its workflow precisely."
    )
    
    # The 'tester' persona doesn't need a real query engine, so we pass None
    # which will cause mission_control logic (if we built it that way) or direct agent
    # instantiation to use a DummyQueryEngine. For this direct CLI command, we can just
    # instantiate the agent directly as it doesn't need mission_control's GitHub features.
    from .core import Agent
    from ..query.engine import QueryEngine # Note: We need a dummy, let's handle this cleanly
    
    class DummyQueryEngine:
        pass

    agent = Agent(query_engine=DummyQueryEngine()) # type: ignore
    
    task = Task(goal=mission, next_input=mission)
    
    # 4. Launch the agent's autonomous loop
    console.print(Panel("[bold green]🤖 Agent execution started...[/bold green]"))
    final_task = agent.mission_loop(task, persona="tester")
    
    console.print(Panel(f"[bold green]✅ Mission Complete[/bold green]"))
    console.print(f"  - Final Status: {final_task.status}")
    console.print(f"  - Final Answer: {final_task.final_answer}")
    console.print(f"\n[cyan]You can find the generated test file in the '{WORKSPACE_PATH}/tests' directory.[/cyan]")


if __name__ == "__main__":
    app()

