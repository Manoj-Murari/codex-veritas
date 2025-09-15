"""
The Agent's Brain: The Core Reasoning and Orchestration Engine.

This module defines the `Agent` class. It includes robust history reconstruction
and a JSON-repair mechanism so the agent can recover when the LLM emits
slightly malformed JSON.
"""

import json
import re
import inspect
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

import google.generativeai as genai
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

# --- Local Imports ---
from ..query.engine import QueryEngine
from . import tools as agent_tools
from . import github_tools
from .task import Task

# --- Configuration & Environment Loading ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def configure_services() -> None:
    """Initializes the connection to the Google Generative AI service."""
    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise KeyError("GOOGLE_API_KEY not found")
        genai.configure(api_key=api_key)
    except KeyError:
        print("--- ❌ ERROR: GOOGLE_API_KEY not found or is empty in your .env file. ---")
        print(f"--- Searched for .env file at: {PROJECT_ROOT / '.env'} ---")
        exit(1)


configure_services()

# --- Constants ---
AGENT_MODEL_NAME = "gemini-1.5-pro-latest"


# --- Pydantic Models for LLM Response Validation ---
class ToolCall(BaseModel):
    tool: str = Field(description="The name of the tool to be called.")
    args: Dict[str, Any] = Field(description="The arguments for the tool.")


class AgentResponse(BaseModel):
    thought: str = Field(description="The agent's reasoning and plan for the next step.")
    action: ToolCall = Field(description="The specific tool call to execute.")


# --- JSON extraction & repair helpers ---


def _extract_json_from_codeblock(text: str) -> Optional[str]:
    """Extract JSON inside ```json ... ``` code block if present."""
    m = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        return m.group(1)
    return None


def _extract_balanced_braces(text: str) -> Optional[str]:
    """Find the first balanced JSON object substring by scanning braces."""
    start = text.find('{')
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        start = text.find('{', start + 1)
    return None


def _heuristic_clean(candidate: str) -> str:
    """
    Apply a few harmless heuristics to try and repair common LLM JSON mistakes:
    - Normalize smart quotes to straight quotes
    - Convert single quotes to double quotes if there are no double quotes already
    - Remove trailing commas before } or ]
    - Strip control characters
    """
    s = candidate
    s = s.replace('“', '"').replace('”', '"').replace('’', "'").replace('—', '-')
    # If there are no double quotes but single quotes exist, swap them
    if '"' not in s and "'" in s:
        s = s.replace("'", '"')
    # Remove trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)
    # Remove stray backticks
    s = s.replace("`", "")
    # Trim non-printable control characters
    s = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", s)
    return s


def safe_parse_json(response_text: str, chat: Optional[Any] = None) -> Dict[str, Any]:
    """
    Attempt to extract and parse a JSON object from the model output. If parsing
    fails and a `chat` object is provided, send a short correction prompt to the
    model asking only for valid JSON and retry parsing.

    Returns:
        a parsed dict

    Raises:
        ValueError if no valid JSON can be recovered.
    """
    # 1) Prefer explicit ```json blocks
    candidate = _extract_json_from_codeblock(response_text)
    if not candidate:
        # 2) Try to extract first balanced {...} block
        candidate = _extract_balanced_braces(response_text)

    if not candidate:
        # 3) Try generic regex fallback (greedy) as last resort
        m = re.search(r'(\{.*\})', response_text, re.DOTALL)
        candidate = m.group(1) if m else None

    if not candidate:
        raise ValueError("No JSON object found in model output.")

    # Try direct parse
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        # Try heuristic cleaning and parse again
        cleaned = _heuristic_clean(candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # If we have a chat interface, ask the model to correct itself
            if chat is not None:
                correction_prompt = (
                    "Your previous response was not valid JSON. "
                    "Please return ONLY a valid JSON object (no explanation, no code fences). "
                    "Original response:\n\n" + response_text
                )
                corrected = chat.send_message(correction_prompt)
                corrected_text = getattr(corrected, "text", str(corrected))
                candidate2 = _extract_json_from_codeblock(corrected_text) or _extract_balanced_braces(corrected_text)
                if not candidate2:
                    m2 = re.search(r'(\{.*\})', corrected_text, re.DOTALL)
                    candidate2 = m2.group(1) if m2 else None
                if not candidate2:
                    raise ValueError("Self-correction attempt did not return a JSON object.")
                try:
                    return json.loads(candidate2)
                except json.JSONDecodeError as e2:
                    # one last heuristic attempt
                    cleaned2 = _heuristic_clean(candidate2)
                    try:
                        return json.loads(cleaned2)
                    except json.JSONDecodeError:
                        raise ValueError(f"JSON parsing failed after self-correction. Last error: {e2}")
            # no chat available or all attempts failed
            raise ValueError(f"JSON parsing failed: {e}")


# --- Agent class ---


class Agent:
    """The core AI agent responsible for reasoning and tool execution."""

    def __init__(self, query_engine: QueryEngine):
        """Initializes the agent with its tools and services."""
        self.query_engine = query_engine
        self.llm = genai.GenerativeModel(AGENT_MODEL_NAME)

        # Tools that the agent may call. If a tool is missing, the agent will return an error
        self.tools: Dict[str, Any] = {
            "list_files": getattr(agent_tools, "list_files", None),
            "read_file": getattr(agent_tools, "read_file", None),
            "write_file": getattr(agent_tools, "write_file", None),
            "add_docstring_to_function": getattr(agent_tools, "add_docstring_to_function", None),
            "query_semantic": getattr(self.query_engine, "query_semantic", None),
            "query_structural": getattr(self.query_engine, "_query_structural", None),
            "get_issue_details": getattr(github_tools, "get_issue_details", None),
            "post_comment_on_issue": getattr(github_tools, "post_comment_on_issue", None),
            "get_pr_changed_files": getattr(github_tools, "get_pr_changed_files", None),
            "get_file_content_from_pr": getattr(github_tools, "get_file_content_from_pr", None),
            "post_pr_review_comment": getattr(github_tools, "post_pr_review_comment", None),
            "parse_code_snippet": getattr(agent_tools, "parse_code_snippet", None),
            "find_similar_code": getattr(agent_tools, "find_similar_code", None),
        }

        # Build prompt-friendly tool list (only include callable ones)
        self.tool_definitions: str = "\n".join(
            [
                f"- `{name}{str(inspect.signature(func))}`: {func.__doc__.strip().splitlines()[0]}"
                for name, func in self.tools.items()
                if callable(func)
            ]
        )

        # System prompts for personas
        self.system_prompts: Dict[str, str] = {
            "default": self._build_default_prompt(),
            "reviewer": self._build_reviewer_prompt(),
            "refactor": self._build_refactor_prompt(),
        }

    def _build_default_prompt(self) -> str:
        """Constructs the general-purpose system prompt."""
        return (
            "You are an expert software engineer agent. Your goal is to complete the user's request by following a strict workflow.\n\n"
            "WORKFLOW:\n"
            "1. THINK: In your thought, reason step-by-step about the user's request and create a plan.\n"
            "2. ACT: Based on your plan, choose a single tool from the AVAILABLE TOOLS list to execute.\n"
            "3. RESPOND: You MUST respond with a single, valid JSON object that follows the RESPONSE FORMAT.\n\n"
            "RESPONSE FORMAT:\n"
            "Your response MUST be a JSON object with two keys: \"thought\" and \"action\". The \"action\" key must contain \"tool\" and \"args\".\n\n"
            "EXAMPLE RESPONSE:\n"
            "{{\n"
            '  "thought": "I need to list files to inspect structure.",\n'
            '  "action": {{ "tool": "list_files", "args": {{ "directory": "." }} }}\n'
            "}}\n\n"
            "RULES:\n"
            "- Follow the workflow and response format exactly.\n"
            "- Use available tools; do not invent side effects.\n"
            "- When done, call the 'finish' tool with the final_answer.\n\n"
            "AVAILABLE_TOOLS:\n"
            f"{self.tool_definitions}\n\n"
            "- finish(final_answer: str): Signals completion.\n"
        )

    def _build_reviewer_prompt(self) -> str:
        """Constructs the specialized system prompt for code reviews."""
        return (
            "You are a world-class AI code reviewer. Provide a structurally-honest review of a GitHub PR.\n\n"
            "WORKFLOW:\n"
            "1. Use get_pr_changed_files to discover changed files.\n"
            "2. For each changed .py file, get_file_content_from_pr and parse_code_snippet.\n"
            "3. If new functions are found, use find_similar_code to check for tests or similar code.\n"
            "4. Summarize findings and post_pr_review_comment. When done, call finish.\n\n"
            "AVAILABLE_TOOLS:\n"
            f"{self.tool_definitions}\n\n"
            "- finish(final_answer: str): Signals completion.\n"
        )

    def _build_refactor_prompt(self) -> str:
        """Constructs the specialized system prompt for multi-step refactoring."""
        return (
            "You are an expert, methodical software refactoring agent.\n\n"
            "REFACTOR WORKFLOW:\n"
            "1. Assess: Use read_file to understand the code.\n"
            "2. Identify: In your thought, identify the single next logical change.\n"
            "3. Execute: Choose the most precise tool for that change (e.g., add_docstring_to_function).\n"
            "4. Plan Next Step: After a successful tool call, state what you did and the next logical step (or finish).\n"
            "5. Repeat until all required changes are complete. Use finish when done.\n\n"
            "RESPONSE FORMAT: Return JSON with keys 'thought' and 'action'.\n\n"
            "EXAMPLE:\n"
            "{{\n"
            '  "thought": "I have read the file. Next: add a docstring to calculate_sum.",\n'
            '  "action": {{ "tool": "add_docstring_to_function", "args": {{ "file_path": "sample_logic.py", "function_name": "calculate_sum", "docstring": "..." }} }}\n'
            "}}\n\n"
            "AVAILABLE_TOOLS:\n"
            f"{self.tool_definitions}\n\n"
            "- finish(final_answer: str): Signals completion.\n"
        )

    def step(self, task: Task, persona: str = "default") -> Task:
        """
        Executes a single step of the reasoning loop for a given Task.

        The Task object is expected to provide:
          - status (str): "running", "completed", or "failed"
          - task_id (str)
          - goal (str)
          - history (list of step records or Step objects)
          - next_input (str)
          - add_step(turn:int, thought:str, action:dict, result:str)
          - final_answer (optional)
        """
        if getattr(task, "status", "") != "running":
            print(f"   - Task {getattr(task, 'task_id', '<unknown>')} is not running. No action taken.")
            return task

        # Build history for the LLM
        system_prompt = self.system_prompts.get(persona, self.system_prompts["default"])
        history_for_llm: List[Dict[str, Any]] = [{"role": "user", "parts": [system_prompt]}]

        # Reconstruct conversation from task.history (accept dicts or objects)
        for step_record in getattr(task, "history", []):
            if isinstance(step_record, dict):
                thought_text = step_record.get("thought", "")
                action_obj = step_record.get("action", {})
                result_text = step_record.get("result", "")
            else:
                # Step Pydantic model or similar object
                thought_text = getattr(step_record, "thought", "")
                action_obj = getattr(step_record, "action", {})
                result_text = getattr(step_record, "result", "")

            history_for_llm.append({
                "role": "model",
                "parts": [json.dumps({"thought": thought_text, "action": action_obj})]
            })
            history_for_llm.append({
                "role": "user",
                "parts": [f"TOOL_RESULT:\n```\n{result_text}\n```"]
            })

        # Start chat with reconstructed history
        chat = self.llm.start_chat(history=history_for_llm)
        current_turn = len(getattr(task, "history", [])) + 1
        print(f"\n--- 🤔 Agent Turn {current_turn} ---")

        try:
            response = chat.send_message(getattr(task, "next_input", ""))
            response_text = getattr(response, "text", str(response))
            print(f"   - Raw LLM Output:\n{response_text}")

            # Parse the JSON robustly (with repair / self-correction fallback)
            parsed = safe_parse_json(response_text, chat=chat)
            validated = AgentResponse(**parsed)

            thought = validated.thought
            tool_call = validated.action

            print(f"   - Thought: {thought}")
            print(f"   - Action: Calling `{tool_call.tool}` with args: {tool_call.args}")

            # Special-case finish
            if tool_call.tool == "finish":
                print("   - ✅ Mission Complete.")
                task.status = "completed"
                task.final_answer = tool_call.args.get("final_answer", "Mission complete.")
                try:
                    task.add_step(current_turn, thought, tool_call.dict(), task.final_answer)
                except Exception:
                    pass
                return task

            # Execute the requested tool if available
            if tool_call.tool in self.tools and callable(self.tools[tool_call.tool]):
                tool_fn = self.tools[tool_call.tool]
                try:
                    result = tool_fn(**tool_call.args)
                except Exception as e:
                    result = f"Tool {tool_call.tool} failed with error: {e}"
                task.next_input = f"TOOL_RESULT:\n```\n{result}\n```"
                try:
                    task.add_step(current_turn, thought, tool_call.dict(), result)
                except Exception:
                    pass
            else:
                result = f"Error: Unknown or unavailable tool named '{tool_call.tool}'."
                task.next_input = f"TOOL_ERROR:\n```\n{result}\n```"
                try:
                    task.add_step(current_turn, thought, tool_call.dict(), result)
                except Exception:
                    pass

        except (ValidationError, ValueError) as e:
            # ValidationError: AgentResponse validation failed
            # ValueError: safe_parse_json raised (no JSON or cannot repair)
            result = f"Error in agent response: {e}"
            print(f"   - ❌ {result}")
            task.next_input = f"RESPONSE_ERROR:\n```\n{result}\n```"
            try:
                task.add_step(current_turn, "Error handling response", {"tool": "error", "args": {}}, result)
            except Exception:
                pass

        except Exception as e:
            # Any other unexpected error
            result = f"An unexpected error occurred: {e}"
            print(f"   - ❌ {result}")
            task.status = "failed"
            task.final_answer = result
            try:
                task.add_step(current_turn, "FATAL ERROR", {"tool": "error", "args": {}}, result)
            except Exception:
                pass

        return task
