"""
The Agent's Task Data Models.

This module defines the Pydantic models that create a structured representation
of an agent's task. This is the core data structure that will be saved and
loaded by the `memory.py` module, effectively serving as the agent's "memory."

The models are:
- `Step`: Represents a single turn in the agent's reasoning loop, capturing
          the thought, the action taken, and the result of that action.
- `Task`: The main dossier for a mission, containing a unique ID, the overall
          goal, the current status, and a complete history of all steps taken.
"""

import uuid
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# --- Pydantic Models for Task State ---

class Step(BaseModel):
    """Represents a single step in the agent's execution history."""
    turn: int
    thought: str
    action: Dict[str, Any]
    result: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class Task(BaseModel):
    """Represents the complete state of an agent's task."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    status: Literal["running", "completed", "failed"] = "running"
    history: List[Step] = Field(default_factory=list)
    final_answer: str | None = None
    
    # The `next_input` field stores what should be fed to the LLM in the next turn.
    # This is crucial for resuming a task.
    next_input: str

    def add_step(self, turn: int, thought: str, action: Dict[str, Any], result: str):
        """Adds a new step to the task's history."""
        step = Step(
            turn=turn,
            thought=thought,
            action=action,
            result=result
        )
        self.history.append(step)
