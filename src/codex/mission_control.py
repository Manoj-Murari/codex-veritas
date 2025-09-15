"""
The Mission Control Script: The Orchestrator.

This module provides the high-level functions that connect the agent's
autonomous capabilities to real-world command-line workflows. It is the
bridge between the user's intent and the agent's execution loop.
"""

import re
import shutil
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

# --- Local Imports ---
from .agent import github_tools
from .agent.core import Agent
from .agent.task import Task
from .agent.tools import WORKSPACE_PATH, write_file


# --- A "Dummy" Engine for Simple, Non-Code-Aware Tasks ---
class DummyQueryEngine:
    """A placeholder query engine for when no analysis files are provided."""

    def query_semantic(self, query_text: str) -> str:
        """(Disabled) Performs a semantic search for code."""
        return "Error: Cannot perform semantic query. No semantic database was provided."

    def _query_structural(self, node_name: str, relations: str) -> str:
        """(Disabled) Queries the code graph for relationships."""
        return "Error: Cannot perform structural query. No code graph was provided."


# --- Main Mission Execution Functions ---

# --- CORRECTED: Added 'persona' argument ---
def execute_mission(issue_url: str, persona: str = "default"):
    """
    The primary, general-purpose mission orchestrator.
    """
    console = Console()
    console.print(Panel("[bold green]🚀 Initializing General Purpose Mission[/bold green]"))

    # 1. Parse Issue URL
    match = re.search(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)", issue_url)
    if not match:
        console.print("[bold red]Error:[/bold red] Invalid GitHub issue URL format.")
        return

    repo_name, issue_number_str = match.groups()
    issue_number = int(issue_number_str)
    console.print(f"  - Repository: {repo_name}\n  - Issue #:    {issue_number}")

    # 2. Fetch Mission from GitHub
    mission_prompt = github_tools.get_issue_details(repo_name, issue_number)
    if mission_prompt.startswith("Error"):
        console.print(f"[bold red]Error fetching mission:[/bold red] {mission_prompt}")
        return
        
    # --- This mission requires the agent's own source code ---
    try:
        if WORKSPACE_PATH.exists():
            shutil.rmtree(WORKSPACE_PATH)
        # Copy the entire 'src' directory into the workspace
        shutil.copytree(Path("src"), WORKSPACE_PATH / "src")
        console.print(f"  - ✅ Workspace populated with project source code.")
    except Exception as e:
        console.print(f"[bold red]Error setting up workspace:[/bold red] {e}")
        return

    # 3. Initialize Agent & Task
    agent = Agent(query_engine=DummyQueryEngine())
    task = Task(goal=mission_prompt, next_input=mission_prompt)

    # 4. Launch Autonomous Loop
    console.print(Panel(f"[bold green]🤖 Agent execution started with '{persona}' persona...[/bold green]"))
    final_task = agent.mission_loop(task, persona=persona)

    # 5. Report Outcome
    console.print(Panel(f"[bold green]✅ Mission Complete[/bold green]"))
    console.print(f"  - Final Status: {final_task.status}")
    console.print(f"  - Final Answer: {final_task.final_answer}")


def create_new_feature_from_issue(issue_url: str):
    """
    The specialized mission orchestrator for creating new features.
    """
    console = Console()
    console.print(Panel("[bold yellow]Fetching Mission Details[/bold yellow]"))

    match = re.search(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)", issue_url)
    if not match:
        console.print("[bold red]Error:[/bold red] Invalid GitHub issue URL format.")
        return

    repo_name, issue_number_str = match.groups()
    issue_number = int(issue_number_str)

    console.print(f"  - Repository: {repo_name}\n  - Issue #:    {issue_number}")

    mission_prompt = github_tools.get_issue_details(repo_name, issue_number)
    if mission_prompt.startswith("Error"):
        console.print(f"[bold red]Error fetching mission:[/bold red] {mission_prompt}")
        return

    try:
        if WORKSPACE_PATH.exists():
            shutil.rmtree(WORKSPACE_PATH)
        WORKSPACE_PATH.mkdir()
        console.print(f"  - ✅ Workspace cleaned and prepared at: {WORKSPACE_PATH}")
    except Exception as e:
        console.print(f"[bold red]Error during workspace setup:[/bold red] {e}")
        return

    console.print(Panel("[bold yellow]🚀 Launching Feature Development Mission[/bold yellow]"))
    agent = Agent(query_engine=DummyQueryEngine())
    task = Task(goal=mission_prompt, next_input=mission_prompt)
    final_task = agent.mission_loop(task, persona="feature_dev")

    console.print(Panel("[bold yellow]📬 Reporting Mission Outcome[/bold yellow]"))
    outcome_report = f"**Mission Status: {final_task.status}**\n\n**Agent's Final Report:**\n{final_task.final_answer}"
    result = github_tools.post_comment_on_issue(repo_name, issue_number, outcome_report)
    console.print(f"  - {result}")

