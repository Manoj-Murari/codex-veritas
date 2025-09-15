"""
The Agent's Memory: The State Management System.

This module is responsible for the persistence of agent tasks. It provides
a simple, file-based mechanism to save the complete state of a task to disk
as a JSON file and to load it back into memory.

This capability is the foundation for enabling agents to perform long-running,
complex tasks that may involve multiple steps or be interrupted and resumed later.
"""

from pathlib import Path
import json

# --- Local Imports ---
from .task import Task

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# Create a dedicated directory for storing task state files.
TASKS_DIR = PROJECT_ROOT / "tasks"
TASKS_DIR.mkdir(exist_ok=True)

# --- Core Functions ---

def save_task(task: Task) -> Path:
    """
    Saves the current state of a task to a JSON file.

    The file is named after the task's unique ID.

    Args:
        task: The Task object to be saved.

    Returns:
        The path to the saved task file.
    """
    file_path = TASKS_DIR / f"{task.task_id}.json"
    try:
        # Pydantic's `model_dump_json` is the standard way to serialize a model.
        # `indent=2` makes the file human-readable for debugging.
        file_path.write_text(task.model_dump_json(indent=2), encoding="utf-8")
        print(f"   - 💾 Task state saved to: {file_path}")
        return file_path
    except Exception as e:
        print(f"--- ❌ ERROR: Failed to save task {task.task_id}. Reason: {e} ---")
        raise

def load_task(task_id: str) -> Task | None:
    """
    Loads a task's state from a JSON file.

    Args:
        task_id: The unique ID of the task to load.

    Returns:
        The loaded Task object, or None if the file is not found or fails parsing.
    """
    file_path = TASKS_DIR / f"{task_id}.json"
    if not file_path.exists():
        print(f"--- ❌ ERROR: No task file found for ID {task_id} at {file_path} ---")
        return None
    
    try:
        # Pydantic's `model_validate_json` is the standard way to deserialize.
        # It automatically validates the data against the Task model's schema.
        json_content = file_path.read_text(encoding="utf-8")
        task = Task.model_validate_json(json_content)
        print(f"   - 📂 Task state successfully loaded for ID: {task_id}")
        return task
    except json.JSONDecodeError as e:
        print(f"--- ❌ ERROR: Failed to parse JSON for task {task_id}. Reason: {e} ---")
        return None
    except Exception as e: # Catches Pydantic validation errors
        print(f"--- ❌ ERROR: Failed to validate data for task {task_id}. Reason: {e} ---")
        return None
