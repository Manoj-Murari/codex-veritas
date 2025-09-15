"""
The Agent's Command Center.

This module provides a command-line interface (CLI) to interact with the
Codex Veritas agent. It is now designed around a stateful, multi-step
task execution model.

The script is responsible for:
1.  `start-task`: Creating a new task, running its first step, and saving the state.
2.  `step-task`: Loading an existing task from memory, running the next step,
    and saving the updated state.
"""

import re
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

# --- Local Imports ---
from ..graph.core import CodeGraph
from ..query.engine import QueryEngine
from .core import Agent
from .task import Task
from .memory import save_task, load_task
from . import tools as agent_tools

# --- CLI Application Initialization ---
app = typer.Typer(
    name="agent",
    help="Codex Veritas: A stateful AI agent for software engineering tasks.",
    add_completion=False,
    rich_markup_mode="markdown"
)

console = Console()

# --- A "Dummy" Engine for Simple, Non-Code-Aware Tasks ---
class DummyQueryEngine:
    """A placeholder query engine for when no analysis files are provided."""
    def query_semantic(self, query_text: str) -> str:
        """(Disabled) Performs a semantic search for code."""
        return "Error: Cannot perform semantic query."
    
    def _query_structural(self, node_name: str, relations: str) -> str:
        """(Disabled) Queries the code graph for relationships."""
        return "Error: Cannot perform structural query."

# --- Helper function to initialize services ---
def _initialize_services(graph_path: Optional[Path], db_path: Optional[Path]) -> QueryEngine | DummyQueryEngine:
    """Helper to set up the necessary engine for the agent."""
    if graph_path and db_path:
        # This part remains for future tasks that might need code-awareness
        return QueryEngine(db_path=db_path, graph_path=graph_path)
    else:
        return DummyQueryEngine()
        
# --- CLI Commands for Sprint 12 ---

@app.command(
    name="start-task",
    help="Create a new agent task, run the first step, and save its state."
)
def start_task(
    goal: Annotated[str, typer.Argument(help="The high-level goal for the agent to achieve.")],
    persona: Annotated[str, typer.Option(help="The agent persona to use (e.g., 'default', 'reviewer', 'refactor').")] = "default"
):
    """
    Creates and initiates a new task for the agent.
    If the persona is 'refactor', it sets up a test file.
    """
    console.print(Panel(f"[bold green]🚀 Starting New Task:[/bold green] [italic]{goal}[/italic]"))

    # --- ADDED FOR SPRINT 13: Setup for refactoring tasks ---
    if persona == "refactor":
        console.print("   - Refactor persona detected. Setting up workspace...")
        test_content = """# sample_logic.py

def calculate_sum(a, b):
    # This function is missing a docstring.
    return a + b

class DataProcessor:
    def __init__(self, data):
        self.data = data

    def process(self):
        # This method is also missing a docstring.
        if not self.data:
            return None
        return sum(self.data)
"""
        try:
            agent_tools.write_file("sample_logic.py", test_content)
            console.print("   - ✅ Successfully created 'sample_logic.py' in workspace.")
        except Exception as e:
            console.print(f"[bold red]Error setting up test file:[/bold red] {e}")
            raise typer.Exit(code=1)

    query_engine = DummyQueryEngine()
    agent = Agent(query_engine)

    task = Task(goal=goal, next_input=f"USER_REQUEST: {goal}")
    console.print(f"   - Task ID created: {task.task_id}")

    updated_task = agent.step(task, persona=persona)
    save_task(updated_task)
    
    if updated_task.status != "running":
        console.print(Panel(f"[bold green]✅ Task '{updated_task.status}' in a single step.[/bold green]"))
        console.print(f"Final Answer: {updated_task.final_answer}")
    else:
        console.print(Panel(f"[bold yellow]👉 Task started. To continue, run:[/bold yellow]\n[cyan]python -m src.codex.agent.main step-task {task.task_id} --persona {persona}[/cyan]"))


@app.command(
    name="step-task",
    help="Load an existing task and execute the next step."
)
def step_task(
    task_id: Annotated[str, typer.Argument(help="The unique ID of the task to continue.")],
    persona: Annotated[str, typer.Option(help="The agent persona to use (e.g., 'default', 'reviewer', 'refactor').")] = "default"
):
    """
    Loads and executes the next step for a previously started task.
    """
    console.print(Panel(f"[bold green]🚀 Continuing Task ID:[/bold green] [italic]{task_id}[/italic]"))

    task = load_task(task_id)
    if not task:
        raise typer.Exit(code=1)

    if task.status != "running":
        console.print(f"[bold yellow]Task has already finished with status: '{task.status}'[/bold yellow]")
        console.print(f"Final Answer: {task.final_answer}")
        raise typer.Exit()
        
    query_engine = DummyQueryEngine()
    agent = Agent(query_engine)

    updated_task = agent.step(task, persona=persona)
    save_task(updated_task)
    
    if updated_task.status != "running":
        console.print(Panel(f"[bold green]✅ Task '{updated_task.status}' after this step.[/bold green]"))
        console.print(f"Final Answer: {updated_task.final_answer}")
    else:
        console.print(Panel(f"[bold yellow]👉 Step complete. To continue, run:[/bold yellow]\n[cyan]python -m src.codex.agent.main step-task {task.task_id} --persona {persona}[/cyan]"))

# --- Main Execution Guard ---
if __name__ == "__main__":
    app()