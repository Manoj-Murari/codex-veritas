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
import json

# --- Local Imports ---
from ..mission_control import execute_mission, create_new_feature_from_issue
from .core import Agent
from .task import Task
from .tools import WORKSPACE_PATH, write_file, create_new_test_file

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
    
    from .core import Agent
    
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

@app.command(
    name="run-tests",
    help="Run the pytest suite in the workspace and have the agent report the results."
)
def run_tests_command():
    """
    Sets up a workspace with a deliberately failing test and runs the debugger agent.
    """
    console.print(Panel("[bold magenta]🚀 Initializing Debugger Mission[/bold magenta]"))

    # 1. Define sample source, test, and config files
    source_code = """
# calculator.py
def add(a, b):
    return a + b

def subtract(a, b):
    # This function has a deliberate bug
    return a + b
"""
    test_code = """
# test_calculator.py
from calculator import add, subtract

def test_add_positive():
    assert add(2, 3) == 5

def test_add_negative():
    assert add(-1, -1) == -2

def test_subtract_correct():
    assert subtract(10, 5) == 5

def test_subtract_bug():
    # This test is designed to fail
    assert subtract(5, 3) == 2
"""
    pytest_config = """
# pyproject.toml
[tool.pytest.ini_options]
pythonpath = ["."]
"""

    try:
        # 2. Prepare a clean workspace and create the files
        if WORKSPACE_PATH.exists():
            shutil.rmtree(WORKSPACE_PATH)
        WORKSPACE_PATH.mkdir()
        
        write_file("calculator.py", source_code)
        write_file("pyproject.toml", pytest_config)
        
        create_new_test_file("test_calculator.py", test_code)
        
        console.print("  - ✅ Workspace prepared with a failing test case and pytest config.")

    except Exception as e:
        console.print(f"[bold red]Error during workspace setup:[/bold red] {e}")
        raise typer.Exit(code=1)

    # 3. Formulate the mission
    mission = "Your goal is to run the tests in the workspace and report a summary of the results. You must use the 'debugger' persona."
    
    from .core import Agent
    
    class DummyQueryEngine:
        pass

    agent = Agent(query_engine=DummyQueryEngine()) # type: ignore
    task = Task(goal=mission, next_input=mission)
    
    # 4. Launch the agent's autonomous loop with the 'debugger' persona
    console.print(Panel("[bold green]🤖 Agent execution started...[/bold green]"))
    final_task = agent.mission_loop(task, persona="debugger")
    
    console.print(Panel(f"[bold green]✅ Mission Complete[/bold green]"))
    console.print(f"  - Final Status: {final_task.status}")
    
    console.print("  - Final Answer:")
    try:
        parsed_answer = json.loads(final_task.final_answer)
        console.print_json(data=parsed_answer)
    except (json.JSONDecodeError, TypeError):
        console.print(final_task.final_answer)

# --- NEW: Command for TDD Bug Fixing (Sprint 17) ---
@app.command(
    name="fix-bug",
    help="Run the TDD agent to write a failing test, fix a bug, and verify."
)
def fix_bug_command():
    """
    Sets up a workspace with buggy code and runs the TDD agent to fix it.
    """
    console.print(Panel("[bold blue]🚀 Initializing TDD Bug Fixing Mission[/bold blue]"))

    # 1. Define buggy source code
    buggy_code = """
# user_profile.py

def get_user_profile(user_id: int):
    \"\"\"
    Retrieves a user's profile from a database.
    For this example, it returns a mock dictionary.
    
    The bug is that it does not include the 'email' field for all users.
    \"\"\"
    if user_id == 1:
        return {"username": "testuser", "email": "test@example.com"}
    else:
        # This is the buggy part
        return {"username": "otheruser"}
"""
    bug_report = (
        "The function `get_user_profile` in `user_profile.py` is buggy. "
        "It's supposed to always return a dictionary with an 'email' key, but it fails to do so for any user ID other than 1. "
        "Your mission is to write a failing test that confirms this bug, then fix the code, and finally, run all tests to prove the fix works."
    )

    try:
        # 2. Prepare a clean workspace and create the files
        if WORKSPACE_PATH.exists():
            shutil.rmtree(WORKSPACE_PATH)
        WORKSPACE_PATH.mkdir()
        
        write_file("user_profile.py", buggy_code)
        
        # Add a pytest config to ensure imports work
        pytest_config = "[tool.pytest.ini_options]\npythonpath = ['.']\n"
        write_file("pyproject.toml", pytest_config)
        
        console.print("  - ✅ Workspace prepared with buggy source code.")

    except Exception as e:
        console.print(f"[bold red]Error during workspace setup:[/bold red] {e}")
        raise typer.Exit(code=1)

    # 3. Formulate the mission
    mission = f"Your goal is to fix a bug, following a strict TDD workflow. Here is the bug report:\n\n{bug_report}"
    
    from .core import Agent
    
    class DummyQueryEngine:
        pass

    agent = Agent(query_engine=DummyQueryEngine()) # type: ignore
    task = Task(goal=mission, next_input=mission)
    
    # 4. Launch the agent's autonomous loop with the 'tdd' persona
    console.print(Panel("[bold green]🤖 Agent execution started...[/bold green]"))
    final_task = agent.mission_loop(task, persona="tdd")
    
    console.print(Panel(f"[bold green]✅ Mission Complete[/bold green]"))
    console.print(f"  - Final Status: {final_task.status}")
    console.print(f"  - Final Answer: {final_task.final_answer}")

if __name__ == "__main__":
    app()

