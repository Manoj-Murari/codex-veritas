"""
The Agent's Command Center.

This module provides the primary command-line interface (CLI) to launch the
Codex Veritas agent on its capstone mission: autonomously resolving a GitHub
issue from end to end.
"""
import shutil
import re
from pathlib import Path
from typing_extensions import Annotated
import typer
from rich.console import Console
from rich.panel import Panel
import git

# --- Local Imports ---
from ..mission_control import execute_mission
from . import tools as agent_tools

# --- CLI Application Initialization ---
app = typer.Typer(
    name="agent",
    help="Codex Veritas: An AI agent for software engineering tasks.",
    add_completion=False,
    rich_markup_mode="markdown"
)

console = Console()

# --- The Final, Unified Command ---

@app.command(
    name="run-mission",
    help="Launch the agent to autonomously resolve a bug described in a GitHub issue."
)
def run_mission_command(
    issue_url: Annotated[str, typer.Argument(help="The full URL of the GitHub issue.")],
):
    """
    Orchestrates the entire end-to-end mission for the Journeyman agent.

    This command will:
    1. Clone the repository from the issue URL.
    2. Set up a secure workspace with all necessary configurations.
    3. Launch the agent with the 'journeyman' persona to fix the bug.
    4. Guide the user through the final `git push` and `create-pr` steps.
    """
    console.print(Panel("[bold magenta]🚀 Initializing Journeyman Capstone Mission[/bold magenta]"))

    # 1. Parse Repo URL from Issue URL
    repo_match = re.search(r"github\.com/([\w.-]+/[\w.-]+)/issues/\d+", issue_url)
    if not repo_match:
        console.print("[bold red]Error:[/bold red] Invalid GitHub issue URL format. Could not extract repository name.")
        raise typer.Exit(code=1)
    repo_name = repo_match.group(1)
    repo_url = f"https://github.com/{repo_name}.git"

    # 2. Clean and prepare workspace by cloning the repo
    if agent_tools.WORKSPACE_PATH.exists():
        shutil.rmtree(agent_tools.WORKSPACE_PATH)
    console.print(f"  - Cloning repository: {repo_url}")
    try:
        git.Repo.clone_from(repo_url, agent_tools.WORKSPACE_PATH)
    except git.exc.GitCommandError as e:
        console.print(f"[bold red]Error:[/bold red] Failed to clone repository. Please check the URL and your permissions.")
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    # 3. Copy necessary config files into the workspace
    # No need to copy Dockerfile if not using Docker for local test runs
    
    # Create pytest config to handle the `src` layout inside the workspace
    pytest_config = "[tool.pytest.ini_options]\npythonpath = [\"src\"]\n"
    (agent_tools.WORKSPACE_PATH / "pyproject.toml").write_text(pytest_config, encoding="utf-8")

    console.print(f"  - ✅ Workspace prepared and configured at: {agent_tools.WORKSPACE_PATH}")

    # 4. Launch the mission via the central orchestrator
    final_task = execute_mission(issue_url=issue_url, persona="journeyman")

    # 5. Guide the user through the final human-in-the-loop steps
    if final_task and final_task.status == "completed":
        console.print(Panel("[bold yellow]Human Action Required: Push and Create PR[/bold yellow]"))
        
        # Extract branch name from agent's final answer for user convenience
        branch_name_match = re.search(r"branch '([\w/-]+)'", final_task.final_answer)
        branch_name = branch_name_match.group(1) if branch_name_match else "<branch_name>"

        console.print("The agent has prepared a local commit. Please review the changes and push the branch to GitHub.")
        console.print(f"\n1. Navigate to the workspace:\n   [cyan]cd {agent_tools.WORKSPACE_PATH}[/cyan]")
        console.print(f"\n2. Push the branch:\n   [cyan]git push --set-upstream origin {branch_name}[/cyan]")
        console.print(f"\n3. Create the Pull Request (replace title and body as needed):\n   [cyan]cd ..[/cyan]")
        console.print(f"   [cyan]poetry run python -m src.codex.agent.main create-pr {repo_name} {branch_name} \"Fix: (Your PR Title)\" \"(Your PR Body)\"[/cyan]\n")


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

