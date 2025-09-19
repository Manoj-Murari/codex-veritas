"""
The Agent's Command Center.

This module provides a command-line interface (CLI) to interact with the
Codex Veritas agent, orchestrating complex, multi-step missions.
"""
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

# --- Local Imports ---
from ..mission_control import execute_mission, create_new_feature_from_issue
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
def run_mission_command(issue_url: str):
    """
    A CLI wrapper that executes a mission based on a GitHub issue.
    """
    execute_mission(issue_url=issue_url, persona="default")

@app.command(
    name="create-feature",
    help="Run a feature development mission from a GitHub issue."
)
def create_feature_command(issue_url: str):
    """
    A CLI wrapper for creating new features based on a GitHub issue.
    """
    create_new_feature_from_issue(issue_url=issue_url)

@app.command(
    name="generate-tests",
    help="Generate pytest tests for a given source file."
)
def generate_tests_command(file_path: Path):
    """
    Sets up a workspace and runs the agent to generate tests for a file.
    """
    console.print(Panel(f"[bold green]🚀 Initializing Test Generation Mission for: {file_path.name}[/bold green]"))
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] Source file not found at: {file_path}")
        raise typer.Exit(code=1)

    # Prepare a clean workspace
    agent_tools.WORKSPACE_PATH.mkdir(exist_ok=True)
    for item in agent_tools.WORKSPACE_PATH.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    console.print(f"  - ✅ Workspace cleaned and prepared at: {agent_tools.WORKSPACE_PATH}")

    # Copy the source file into the workspace
    shutil.copy(file_path, agent_tools.WORKSPACE_PATH / file_path.name)
    console.print(f"  - ✅ Copied source file to workspace: {file_path.name}")

    mission = f"Your goal is to generate a complete pytest test file for the code in workspace/{file_path.name}. You must use the 'tester' persona."

    console.print(Panel("[bold green]🤖 Agent execution started...[/bold green]"))
    execute_mission(mission=mission, persona="tester")

@app.command(
    name="run-tests",
    help="Run the test suite in a prepared workspace."
)
def run_tests_command():
    """
    Sets up a workspace with a failing test and runs the debugger agent.
    """
    console.print(Panel("[bold yellow]🚀 Initializing Debugger Mission[/bold yellow]"))
    # Setup workspace
    agent_tools.WORKSPACE_PATH.mkdir(exist_ok=True)
    for item in agent_tools.WORKSPACE_PATH.iterdir():
        shutil.rmtree(item) if item.is_dir() else item.unlink()

    # Create buggy code
    buggy_code = (
        "def subtract(a, b):\n"
        "    \"\"\"This function is deliberately buggy.\"\"\"\n"
        "    return a + b  # The bug is here\n"
    )
    (agent_tools.WORKSPACE_PATH / "calculator.py").write_text(buggy_code, encoding="utf-8")

    # Create test file
    (agent_tools.WORKSPACE_PATH / "tests").mkdir()
    test_code = (
        "from calculator import subtract\n\n"
        "def test_subtract_correct():\n"
        "    assert subtract(10, 5) == 5\n\n"
        "def test_subtract_bug():\n"
        "    assert subtract(5, 3) == 2\n"
    )
    (agent_tools.WORKSPACE_PATH / "tests" / "test_calculator.py").write_text(test_code, encoding="utf-8")

    # Create pytest config
    (agent_tools.WORKSPACE_PATH / "pyproject.toml").write_text("[tool.pytest.ini_options]\npythonpath=[\".\"]", encoding="utf-8")

    console.print("  - ✅ Workspace prepared with a failing test case and pytest config.")

    mission = "Your goal is to run the tests in the workspace and report a summary of the results. You must use the 'debugger' persona."

    console.print(Panel("[bold green]🤖 Agent execution started...[/bold green]"))
    execute_mission(mission=mission, persona="debugger")

@app.command(
    name="fix-bug",
    help="Run the full TDD workflow to fix a bug."
)
def fix_bug_command():
    """
    Sets up a workspace with buggy code and runs the TDD agent to fix it.
    """
    console.print(Panel("[bold magenta]🚀 Initializing TDD Bug Fixing Mission[/bold magenta]"))
    # Setup workspace with a professional structure
    shutil.rmtree(agent_tools.WORKSPACE_PATH, ignore_errors=True)
    src_dir = agent_tools.WORKSPACE_PATH / "src"
    tests_dir = agent_tools.WORKSPACE_PATH / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    # Create __init__.py files to make them packages
    (src_dir / "__init__.py").touch()
    (tests_dir / "__init__.py").touch()

    # Create buggy code in the src directory
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
        "        # This version is deliberately buggy\n"
        "        return {\"username\": \"otheruser\"}\n"
    )
    (src_dir / "user_profile.py").write_text(buggy_code, encoding="utf-8")

    # Create pytest config to find the src package
    pytest_config = (
        "[tool.pytest.ini_options]\n"
        "pythonpath = [\"src\"]\n"
    )
    (agent_tools.WORKSPACE_PATH / "pyproject.toml").write_text(pytest_config, encoding="utf-8")

    console.print("  - ✅ Workspace prepared with buggy source code.")

    mission = "Your mission is to fix a bug in `src/user_profile.py`. The bug is that the function `get_user_profile` does not return an 'email' key for user IDs other than 1. You must use the 'TDD' persona and follow its workflow precisely."

    console.print(Panel("[bold green]🤖 Agent execution started...[/bold green]"))
    execute_mission(mission=mission, persona="tdd")

if __name__ == "__main__":
    app()

