"""
The Mission Control Orchestrator.

This module is the high-level entry point for launching the agent on autonomous
missions. It connects the agent's capabilities to real-world triggers, like
a GitHub issue, and manages the end-to-end execution workflow.
"""
import re
import shutil
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

# --- Local Imports ---
from .agent.core import Agent
from .agent.task import Task
from .agent.memory import save_task, load_task
from .agent.github_tools import get_issue_details, post_comment_on_issue
# --- Removed the faulty import ---

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORKSPACE_PATH = PROJECT_ROOT / "workspace"
CONSOLE = Console()

# --- NEW: Self-Contained Dummy Engine ---
class DummyQueryEngine:
    """A placeholder query engine for when no analysis files are provided."""

    def query_semantic(self, query_text: str) -> str:
        """(Disabled) Performs a semantic search for code."""
        return "Error: Cannot perform semantic query. No semantic database was provided."

    def _query_structural(self, node_name: str, relations: str) -> str:
        """(Disabled) Queries the code graph for relationships."""
        return "Error: Cannot perform structural query. No code graph was provided."


# --- Helper Functions ---

def _setup_mission(issue_url: str) -> tuple[str, int, str]:
    """Parses issue URL and fetches mission details."""
    match = re.search(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)", issue_url)
    if not match:
        raise ValueError("Invalid GitHub issue URL format.")

    repo_name, issue_number_str = match.groups()
    issue_number = int(issue_number_str)

    CONSOLE.print(Panel(f"[bold blue]Fetching Mission Details[/bold blue]"))
    CONSOLE.print(f"  - Repository: {repo_name}")
    CONSOLE.print(f"  - Issue #:    {issue_number}")

    mission_prompt = get_issue_details(repo_name, issue_number)
    if mission_prompt.startswith("Error:"):
        raise ConnectionError(f"Failed to fetch issue details: {mission_prompt}")

    # Clean and prepare the workspace for a new mission
    if WORKSPACE_PATH.exists():
        shutil.rmtree(WORKSPACE_PATH)
    WORKSPACE_PATH.mkdir(exist_ok=True)
    CONSOLE.print(f"  - ✅ Workspace cleaned and prepared at: {WORKSPACE_PATH}")

    return repo_name, issue_number, mission_prompt

# --- Primary Mission Execution Functions ---

def execute_mission(issue_url: str):
    """
    Orchestrates a refactoring/debugging mission from a GitHub issue.
    """
    repo_name, issue_number, mission_prompt = _setup_mission(issue_url)

    CONSOLE.print(Panel("[bold green]🚀 Launching Refactoring Mission[/bold green]"))
    agent = Agent(DummyQueryEngine())
    initial_task = Task(goal=mission_prompt, next_input=mission_prompt)
    save_task(initial_task)

    # Launch the agent with the 'refactor' persona
    final_task = agent.mission_loop(initial_task, persona="refactor")

    CONSOLE.print(Panel("[bold blue]📬 Reporting Mission Outcome[/bold blue]"))
    final_report = (
        f"**Mission Status: {final_task.status.upper()}**\n\n"
        f"**Agent's Final Report:**\n"
        f"```\n{final_task.final_answer}\n```"
    )
    result = post_comment_on_issue(repo_name, issue_number, final_report)
    CONSOLE.print(f"  - {result}")

def create_new_feature_from_issue(issue_url: str):
    """
    Orchestrates a new feature development mission from a GitHub issue.
    """
    repo_name, issue_number, mission_prompt = _setup_mission(issue_url)

    CONSOLE.print(Panel("[bold yellow]🚀 Launching Feature Development Mission[/bold yellow]"))
    agent = Agent(DummyQueryEngine())

    # The goal includes instructions to use the new tool.
    feature_goal = (
        "Your mission is to create a new feature based on the following request.\n"
        "You must use the `create_new_file` tool to write the new code.\n\n"
        f"--- GitHub Issue ---\n{mission_prompt}"
    )
    initial_task = Task(goal=feature_goal, next_input=feature_goal)
    save_task(initial_task)

    # Launch the agent with the specialized 'feature_dev' persona
    final_task = agent.mission_loop(initial_task, persona="feature_dev")

    CONSOLE.print(Panel("[bold blue]📬 Reporting Mission Outcome[/bold blue]"))
    final_report = (
        f"**Mission Status: {final_task.status.upper()}**\n\n"
        f"**Agent's Final Report:**\n"
        f"```\n{final_task.final_answer}\n```"
    )
    result = post_comment_on_issue(repo_name, issue_number, final_report)
    CONSOLE.print(f"  - {result}")

