"""
The Agent's Local Git Toolkit.

This module provides a set of tools for the agent to interact with a local
Git repository within its secure workspace. It uses the GitPython library to
encapsulate common Git commands into a simple, high-level API.
"""

from pathlib import Path
from typing import List
import git

# --- Local Imports ---
from . import tools as agent_tools

# --- Core Functions ---

def _get_repo() -> git.Repo | str:
    """Helper function to safely initialize and return the git.Repo object."""
    try:
        if not (agent_tools.WORKSPACE_PATH / ".git").exists():
            return "Error: The workspace is not a valid Git repository."
        return git.Repo(agent_tools.WORKSPACE_PATH)
    except Exception as e:
        return f"Error initializing Git repository: {e}"

def create_branch(branch_name: str) -> str:
    """Creates and checks out a new local branch in the workspace's repository."""
    repo = _get_repo()
    if isinstance(repo, str):
        return repo # Return the error string

    try:
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()
        return f"Success: Branch '{branch_name}' created and checked out."
    except Exception as e:
        return f"Error creating branch: {e}"

def add_files_to_commit(file_paths: List[str]) -> str:
    """Takes a list of file paths and stages them for the next commit."""
    repo = _get_repo()
    if isinstance(repo, str):
        return repo

    try:
        # We need to resolve the full path within the workspace for GitPython
        full_paths = [agent_tools.WORKSPACE_PATH / p for p in file_paths]
        
        # Check if all files exist before adding
        for p in full_paths:
            if not p.exists():
                return f"Error: File '{p.relative_to(agent_tools.WORKSPACE_PATH)}' not found in workspace."

        repo.index.add([str(p) for p in full_paths])
        return f"Success: Staged {len(file_paths)} file(s): {', '.join(file_paths)}"
    except Exception as e:
        return f"Error staging files: {e}"

def commit_changes(message: str) -> str:
    """Creates a new commit with the staged files and a given commit message."""
    repo = _get_repo()
    if isinstance(repo, str):
        return repo

    try:
        commit = repo.index.commit(message)
        return f"Success: Committed changes with hash {commit.hexsha[:7]}."
    except Exception as e:
        return f"Error committing changes: {e}"
