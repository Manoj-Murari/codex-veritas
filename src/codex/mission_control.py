"""
The Mission Control Orchestrator.

This module is the high-level entry point for launching the agent on its
autonomous missions. It handles parsing inputs, setting up the agent's
workspace and memory, and launching the correct persona for the mission.
"""
import shutil
import re
from pathlib import Path
import json

# --- Local Imports ---
from .agent.core import Agent
from .agent.task import Task
from .agent.memory import save_task
from .agent import github_tools
from .agent import tools as agent_tools
from rich.console import Console
from rich.panel import Panel

console = Console()

# --- DEFINITIVE FIX: Define DummyQueryEngine where it's used ---
class DummyQueryEngine:
    """A placeholder query engine for when no analysis files are provided."""
    def query_semantic(self, query_text: str) -> str:
        return "Error: Cannot perform semantic query. No semantic database was provided."
    def _query_structural(self, node_name: str, relations: str) -> str:
        return "Error: Cannot perform structural query. No code graph was provided."


def execute_mission(mission: str = None, issue_url: str = None, persona: str = "default"):
    """
    Orchestrates a general-purpose agent mission, either from a GitHub issue
    or a direct command.
    """
    repo_name = None
    issue_number = None
    goal = mission

    if issue_url:
        console.print(Panel(f"[bold green]🚀 Initializing Mission from GitHub Issue[/bold green]"))
        match = re.search(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)", issue_url)
        if not match:
            console.print("[bold red]Error:[/bold red] Invalid GitHub issue URL format.")
            return
        repo_name, issue_number = match.groups()
        console.print(f"  - Repository: {repo_name}\n  - Issue #:    {issue_number}")
        goal = github_tools.get_issue_details(repo_name, int(issue_number))
    
    if not goal:
        console.print("[bold red]Error:[/bold red] Mission goal not provided or found.")
        return

    # For general missions that read the codebase, we copy it into the workspace
    if persona == "default":
        if agent_tools.WORKSPACE_PATH.exists():
            shutil.rmtree(agent_tools.WORKSPACE_PATH)
        shutil.copytree("src", agent_tools.WORKSPACE_PATH / "src")
        console.print(f"  - ✅ Workspace populated with project source code.")
    
    console.print(Panel(f"[bold green]🤖 Agent execution started with '{persona}' persona...[/bold green]"))
    
    agent = Agent(query_engine=DummyQueryEngine())
    task = Task(goal=goal, next_input=goal)
    save_task(task)
    
    final_task = agent.mission_loop(task, persona=persona)
    
    console.print(Panel("[bold green]✅ Mission Complete[/bold green]"))
    console.print(f"  - Final Status: {final_task.status}")
    
    # Pretty print the final answer, especially if it's JSON
    try:
        # The agent's final answer for some tasks IS a JSON string.
        final_answer_data = json.loads(final_task.final_answer)
        console.print("  - Final Answer:")
        console.print_json(data=final_answer_data)
    except (json.JSONDecodeError, TypeError):
        # If it's not JSON, print it as regular text.
        console.print(f"  - Final Answer:\n[cyan]{final_task.final_answer}[/cyan]")

    if repo_name and issue_number and final_task.status == "completed":
        console.print(Panel("[bold blue]📬 Reporting Mission Outcome to GitHub...[/bold blue]"))
        report = f"### Codex Veritas Mission Report\n**Status:** {final_task.status}\n\n**Outcome:**\n```\n{final_task.final_answer}\n```"
        github_tools.post_comment_on_issue(repo_name, int(issue_number), report)

def create_new_feature_from_issue(issue_url: str):
    """Orchestrates the 'create-feature' mission."""
    execute_mission(issue_url=issue_url, persona="feature_dev")

# --- CORRECTED: The orchestrator now handles the setup for the TDD mission ---
def execute_fix_bug_mission():
    """Sets up a workspace with a bug and runs the 'TDD' agent."""
    console.print(Panel("[bold magenta]🚀 Initializing TDD Bug Fixing Mission[/bold magenta]"))

    # 1. Clean and prepare workspace
    if agent_tools.WORKSPACE_PATH.exists():
        shutil.rmtree(agent_tools.WORKSPACE_PATH)
    agent_tools.WORKSPACE_PATH.mkdir()

    # 2. Create a professional project structure within the workspace
    src_dir = agent_tools.WORKSPACE_PATH / "src"
    tests_dir = agent_tools.WORKSPACE_PATH / "tests"
    src_dir.mkdir()
    tests_dir.mkdir()
    (src_dir / "__init__.py").touch()

    # 3. Create the buggy source file in the correct location
    buggy_code = (
        "# src/user_profile.py\n\n"
        "def get_user_profile(user_id: int):\n"
        "    \"\"\"\n"
        "    Retrieves a user's profile from a database.\n"
        "    For this example, it returns a mock dictionary.\n"
        "    \"\"\"\n"
        "    if user_id == 1:\n"
        "        return {\"username\": \"testuser\", \"email\": \"test@example.com\"}\n"
        "    else:\n"
        "        return {\"username\": \"otheruser\"} # Missing email key\n"
    )
    (src_dir / "user_profile.py").write_text(buggy_code, encoding="utf-8")

    # 4. Create the pytest config to handle the `src` layout
    pytest_config = "[tool.pytest.ini_options]\npythonpath = [\"src\"]\n"
    (agent_tools.WORKSPACE_PATH / "pyproject.toml").write_text(pytest_config, encoding="utf-8")
    
    console.print("  - ✅ Workspace prepared with buggy source code.")

    mission = (
        "There is a bug in `src/user_profile.py`. The function `get_user_profile` "
        "does not return an 'email' key for user IDs other than 1. Your goal is "
        "to fix this bug. You must use the 'TDD' persona and follow its workflow precisely."
    )
    
    # 5. Launch the mission
    execute_mission(mission=mission, persona="tdd")

