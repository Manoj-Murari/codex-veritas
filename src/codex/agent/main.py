"""
The Agent's Command Center.

This module provides a command-line interface (CLI) to orchestrate and
launch the Codex Veritas agent on various autonomous missions.
"""
import shutil
from pathlib import Path
from typing_extensions import Annotated
import typer
from rich.console import Console
from rich.panel import Panel
import git

# --- Local Imports ---
from ..mission_control import (
    execute_mission, 
    create_new_feature_from_issue,
    execute_fix_bug_mission
)
from . import tools as agent_tools

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
    """A CLI wrapper that executes a mission based on a GitHub issue."""
    execute_mission(issue_url=issue_url, persona="default")

@app.command(
    name="create-feature",
    help="Create a new feature based on a GitHub issue."
)
def create_feature_command(
    issue_url: Annotated[str, typer.Argument(help="The full URL of the GitHub issue for the new feature.")],
):
    """A CLI wrapper for the 'feature_dev' persona."""
    create_new_feature_from_issue(issue_url=issue_url)

@app.command(
    name="fix-bug",
    help="Launch the TDD agent to write a test, fix a bug, and verify."
)
def fix_bug_command():
    """A simple CLI wrapper that calls the dedicated TDD mission orchestrator."""
    # All complex setup logic is now handled in mission_control.py
    execute_fix_bug_mission()

# --- NEW: Two-Part Command for Creating a Pull Request (Sprint 19) ---

@app.command(
    name="prepare-pr",
    help="Have the agent perform a task and prepare a local branch for a PR."
)
def prepare_pr_command(
    repo_url: Annotated[str, typer.Argument(help="The HTTPS URL of the repo to clone.")],
    task_prompt: Annotated[str, typer.Argument(help="The specific task for the agent to perform.")],
):
    """
    Sets up a repo, runs an agent to perform a task, and prepares a local
    commit on a new branch, ready for a human to push.
    """
    console.print(Panel(f"[bold blue]🚀 Initializing Pull Request Preparation Mission[/bold blue]"))
    
    # 1. Clean and prepare workspace by cloning the repo
    if agent_tools.WORKSPACE_PATH.exists():
        shutil.rmtree(agent_tools.WORKSPACE_PATH)
    console.print(f"  - Cloning repository: {repo_url}")
    git.Repo.clone_from(repo_url, agent_tools.WORKSPACE_PATH)
    console.print(f"  - ✅ Workspace prepared at: {agent_tools.WORKSPACE_PATH}")

    console.print(Panel("[bold green]🤖 Agent execution started with 'pr_creator' persona...[/bold green]"))
    
    # --- Local imports to avoid circular dependency issues ---
    from .core import Agent, Task
    from .memory import save_task, load_task
    from ..mission_control import DummyQueryEngine

    # Create and run the mission
    agent = Agent(query_engine=DummyQueryEngine())
    task = Task(goal=task_prompt, next_input=task_prompt)
    save_task(task)
    
    final_task = agent.mission_loop(task, persona="pr_creator")
    
    console.print(Panel("[bold green]✅ Agent Work Complete[/bold green]"))
    console.print(f"  - Final Status: {final_task.status}")
    console.print("  - Final Answer:")
    console.print(f"[cyan]{final_task.final_answer}[/cyan]")
    console.print(f"\n[bold yellow]Please cd into '{agent_tools.WORKSPACE_PATH}', inspect the changes, and then run 'git push --set-upstream origin <branch_name>'[/bold yellow]")
    console.print(f"[bold yellow]Then, run the 'create-pr' command.[/bold yellow]")


@app.command(
    name="create-pr",
    help="Create the pull request on GitHub after the branch has been pushed."
)
def create_pr_command(
    repo_name: Annotated[str, typer.Argument(help="The full repo name (e.g., 'Manoj-Murari/codex-veritas').")],
    branch_name: Annotated[str, typer.Argument(help="The name of the branch that was just pushed.")],
    title: Annotated[str, typer.Argument(help="The title for the pull request.")],
    body: Annotated[str, typer.Argument(help="The body/description for the pull request.")],
):
    """A simple CLI wrapper for the create_pull_request tool."""
    console.print(Panel(f"[bold blue]🚀 Creating Pull Request on GitHub[/bold blue]"))
    
    from . import github_tools
    result = github_tools.create_pull_request(
        repo_name=repo_name,
        branch_name=branch_name,
        title=title,
        body=body
    )
    console.print(f"  - Result: [green]{result}[/green]")


if __name__ == "__main__":
    app()

