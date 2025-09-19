"""
The Mission Control Orchestrator.

This module is the high-level entry point for launching the agent on autonomous
missions. It handles the setup, execution, and reporting for different types
of missions, acting as the bridge between the user's command and the agent's
core reasoning loop.
"""

import re
import shutil
import json  # --- FIX: Import the json module ---
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel

# --- Local Imports ---
from .agent.core import Agent, Task
from .agent.memory import save_task
from .agent import github_tools
from .agent import tools as agent_tools

# --- A "Dummy" Engine for Simple, Non-Code-Aware Tasks ---
class DummyQueryEngine:
    """A placeholder query engine for when no analysis files are provided."""
    def query_semantic(self, query_text: str) -> str:
        return "Error: No semantic database was provided."
    def _query_structural(self, node_name: str, relations: str) -> str:
        return "Error: No code graph was provided."

console = Console()

# --- CORRECTED & UPGRADED: Main Mission Executor (Sprint 17/18) ---
def execute_mission(
    persona: str,
    issue_url: Optional[str] = None,
    mission: Optional[str] = None
):
    """
    Orchestrates a full agent mission, either from a GitHub issue or a direct command.
    """
    if not issue_url and not mission:
        console.print("[bold red]Error: Mission failed. Must provide either a GitHub issue URL or a direct mission string.[/bold red]")
        return

    goal = ""
    repo_name = None
    issue_number = None

    if issue_url:
        console.print(Panel(f"[bold green]🚀 Initializing General Purpose Mission[/bold green]"))
        match = re.search(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)", issue_url)
        if not match:
            console.print("[bold red]Error: Invalid GitHub issue URL format.[/bold red]")
            return
        repo_name, issue_number_str = match.groups()
        issue_number = int(issue_number_str)
        console.print(f"  - Repository: {repo_name}")
        console.print(f"  - Issue #:    {issue_number}")
        
        goal = github_tools.get_issue_details(repo_name, issue_number)
        if goal.startswith("Error"):
            console.print(f"[bold red]Failed to fetch mission details: {goal}[/bold red]")
            return

        # For GitHub missions, populate the workspace with the project's source
        shutil.rmtree(agent_tools.WORKSPACE_PATH, ignore_errors=True)
        shutil.copytree("src", agent_tools.WORKSPACE_PATH / "src")
        console.print("  - ✅ Workspace populated with project source code.")
    else:
        # This is for direct missions like fix-bug
        goal = mission

    console.print(Panel(f"[bold green]🤖 Agent execution started with '{persona}' persona...[/bold green]"))
    
    agent = Agent(query_engine=DummyQueryEngine())
    task = Task(goal=goal, next_input=goal)
    save_task(task)

    final_task = agent.mission_loop(task, persona=persona)

    console.print(Panel("[bold green]✅ Mission Complete[/bold green]"))
    console.print(f"  - Final Status: {final_task.status}")
    
    # Pretty print the final answer, especially if it's JSON
    try:
        final_answer_json = json.loads(final_task.final_answer)
        console.print_json(data=final_answer_json)
    except (json.JSONDecodeError, TypeError):
        console.print(f"  - Final Answer:\n{final_task.final_answer}")


    if repo_name and issue_number and final_task.status == "completed":
        console.print(Panel("[bold blue]📬 Reporting Mission Outcome[/bold blue]"))
        report_body = (
            f"### ✅ Mission Complete\n\n"
            f"**Agent Status:** {final_task.status}\n\n"
            f"**Final Report:**\n"
            f"```\n{final_task.final_answer}\n```"
        )
        result = github_tools.post_comment_on_issue(repo_name, issue_number, report_body)
        console.print(f"  - {result}")

def create_new_feature_from_issue(issue_url: str):
    """
    High-level orchestrator for the 'create-feature' command.
    """
    console.print(Panel("[bold cyan]🚀 Launching Feature Development Mission[/bold cyan]"))
    execute_mission(issue_url=issue_url, persona="feature_dev")

