"""
The Agent's Brain: The Core Reasoning and Orchestration Engine.

This module defines the `Agent` class. It supports:
- robust history reconstruction (works with dicts or Step objects),
- resilient JSON extraction and self-correction,
- a `step` method that executes one reasoning/tool cycle,
- an autonomous `mission_loop` that runs until completion or failure.
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
from .memory import save_task

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


# --- Pydantic models for validation of LLM responses ---


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
    return m.group(1) if m else None


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
    Apply heuristics to repair common LLM JSON mistakes:
    - Normalize smart quotes to straight quotes
    - Optionally convert single quotes to double quotes if safe
    - Remove trailing commas before } or ]
    - Strip control characters and stray backticks
    """
    s = candidate
    s = s.replace('“', '"').replace('”', '"').replace('’', "'").replace('—', '-')
    if '"' not in s and "'" in s:
        s = s.replace("'", '"')
    s = re.sub(r",\s*([}\]])", r"\1", s)
    s = s.replace("`", "")
    s = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", s)
    return s


def safe_parse_json(response_text: str, chat: Optional[Any] = None) -> Dict[str, Any]:
    """
    Attempt to extract and parse JSON from model output. If parsing fails and a
    `chat` object is provided, request a corrected JSON-only response from the model.

    Returns:
        Parsed dict

    Raises:
        ValueError if no valid JSON can be recovered.
    """
    candidate = _extract_json_from_codeblock(response_text)
    if not candidate:
        candidate = _extract_balanced_braces(response_text)

    if not candidate:
        m = re.search(r'(\{.*\})', response_text, re.DOTALL)
        candidate = m.group(1) if m else None

    if not candidate:
        raise ValueError("No JSON object found in model output.")

    # Try raw parse
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        # Try cleaned parse
        cleaned = _heuristic_clean(candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # If a chat interface is available, ask model to correct itself
            if chat is not None:
                correction_prompt = (
                    "Your previous response was not valid JSON. "
                    "Please return ONLY a valid JSON object (no explanation, no code fences).\n\n"
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
                    cleaned2 = _heuristic_clean(candidate2)
                    try:
                        return json.loads(cleaned2)
                    except json.JSONDecodeError:
                        raise ValueError(f"JSON parsing failed after self-correction. Last error: {e2}")
            raise ValueError(f"JSON parsing failed: {e}")


# --- Core Agent ---


class Agent:
    """The core AI agent responsible for reasoning and tool execution."""

    def __init__(self, query_engine: QueryEngine):
        """Initialize the agent with tools, LLM, and prompts."""
        self.query_engine = query_engine
        self.llm = genai.GenerativeModel(AGENT_MODEL_NAME)

        # Register tools (use getattr for graceful missing-tool behavior)
        self.tools: Dict[str, Any] = {
            "list_files": getattr(agent_tools, "list_files", None),
            "read_file": getattr(agent_tools, "read_file", None),
            "write_file": getattr(agent_tools, "write_file", None),
            "create_new_file": getattr(agent_tools, "create_new_file", None),
            "create_new_test_file": getattr(agent_tools, "create_new_test_file", None),
            "run_tests": getattr(agent_tools, "run_tests", None),
            "add_docstring_to_function": getattr(agent_tools, "add_docstring_to_function", None),
            "get_issue_details": getattr(github_tools, "get_issue_details", None),
            "post_comment_on_issue": getattr(github_tools, "post_comment_on_issue", None),
            "get_pr_changed_files": getattr(github_tools, "get_pr_changed_files", None),
            "get_file_content_from_pr": getattr(github_tools, "get_file_content_from_pr", None),
            "post_pr_review_comment": getattr(github_tools, "post_pr_review_comment", None),
        }

        self.tool_definitions = "\n".join(
            [
                f"- `{name}{str(inspect.signature(func))}`: {func.__doc__.strip().splitlines()[0]}"
                for name, func in self.tools.items()
                if callable(func)
            ]
        )

        self.system_prompts: Dict[str, str] = {
            "default": self._build_default_prompt(),
            "reviewer": self._build_reviewer_prompt(),
            "refactor": self._build_refactor_prompt(),
            "feature_dev": self._build_feature_dev_prompt(),
            "tester": self._build_tester_prompt(),
            "debugger": self._build_debugger_prompt(),
            "tdd": self._build_tdd_prompt(),
        }

    def _build_default_prompt(self) -> str:
        """Default persona prompt used for general tasks."""
        return (
            "You are an expert software engineer agent. Follow the workflow and return responses in strict JSON.\n\n"
            "RESPONSE FORMAT: {\"thought\": \"...\", \"action\": {\"tool\": \"name\", \"args\": {...}}}\n\n"
            "AVAILABLE_TOOLS:\n" + self.tool_definitions + "\n"
            "When finished, use the `finish` tool with final_answer."
        )

    def _build_reviewer_prompt(self) -> str:
        """Persona prompt for code review tasks."""
        return (
            "You are a world-class AI code reviewer. Use the available tools to inspect changed files in a PR and post structured review comments.\n\n"
            "AVAILABLE_TOOLS:\n" + self.tool_definitions + "\n"
            "When done, call `finish(final_answer=...)`."
        )

    def _build_refactor_prompt(self) -> str:
        """Persona prompt for methodical multi-step refactoring tasks."""
        return (
            "You are an expert, methodical software refactoring agent.\n\n"
            "WORKFLOW:\n"
            "1. Assess with read_file.\n"
            "2. Identify one next logical change in your thought.\n"
            "3. Execute the change using the most precise tool.\n"
            "4. After success, state what you did and the next step (or finish).\n\n"
            "Return JSON: {\"thought\": \"...\", \"action\": {\"tool\": \"...\", \"args\": {...}}}\n\n"
            "AVAILABLE_TOOLS:\n" + self.tool_definitions + "\n"
        )

    def _build_feature_dev_prompt(self) -> str:
        """Persona prompt for developing new features."""
        return (
            "You are an expert AI software developer. Your task is to create a new feature by writing a new file.\n\n"
            "WORKFLOW:\n"
            "1. Plan the full file path and content for the new feature.\n"
            "2. Use the `create_new_file` tool to write the complete code into the specified file.\n"
            "3. After successfully creating the file, use the `finish` tool to report your success.\n\n"
            "Return JSON: {\"thought\": \"...\", \"action\": {\"tool\": \"...\", \"args\": {...}}}\n\n"
            "AVAILABLE_TOOLS:\n" + self.tool_definitions + "\n"
        )

    def _build_tester_prompt(self) -> str:
        """Persona prompt for generating new unit tests."""
        return (
            "You are an expert Test Architect specializing in `pytest`.\n\n"
            "WORKFLOW:\n"
            "1. **Analyze:** First, use `read_file` to analyze the source code file you need to test.\n"
            "2. **Identify Targets:** In your thought process, identify all public functions and methods in the file.\n"
            "3. **Generate & Synthesize:** For each target, generate a basic but complete pytest test case. Combine all generated tests into a single, syntactically correct Python file string. Your generated code MUST include all necessary imports.\n"
            "4. **Save Test File:** Use the `create_new_test_file` tool to save the complete test code to a new file. The test filename MUST start with `test_`.\n"
            "5. **Finish:** Once the test file is created, use the `finish` tool.\n\n"
            "Return JSON: {\"thought\": \"...\", \"action\": {\"tool\": \"...\", \"args\": {...}}}\n\n"
            "AVAILABLE_TOOLS:\n" + self.tool_definitions + "\n"
        )

    def _build_debugger_prompt(self) -> str:
        """Persona prompt for running tests and interpreting the output."""
        return (
            "You are an expert AI Debugger. Your task is to run a test suite and interpret the results.\n\n"
            "WORKFLOW:\n"
            "1. **Execute:** Run the `run_tests` tool. This is your only first action.\n"
            "2. **Analyze:** Scrutinize the text output from the tool.\n"
            "3. **Conclude & Finish:** Use the `finish` tool. The `final_answer` argument for this tool MUST be a JSON string containing:\n"
            "   - A `status` field: 'PASSED', 'FAILED', or 'ERROR'.\n"
            "   - If FAILED or ERROR, an `error_summary` field with the names of failed tests and their specific error messages.\n\n"
            "Return JSON: {\"thought\": \"...\", \"action\": {\"tool\": \"...\", \"args\": {...}}}\n\n"
            "AVAILABLE_TOOLS:\n" + self.tool_definitions + "\n"
        )

    # --- CORRECTED: Persona for TDD Bug Fixing (Sprint 17) ---
    def _build_tdd_prompt(self) -> str:
        """Persona prompt for fixing a bug using a strict TDD workflow."""
        return (
            "You are an expert AI Software Engineer specializing in Test-Driven Development (TDD).\n\n"
            "WORKFLOW:\n"
            "1. **Isolate Code:** First, use `read_file` to get the content of the source file containing the bug.\n"
            "2. **Write Failing Test:** Based on the bug report and source code, generate a new pytest function that specifically triggers the bug. Use `create_new_test_file` to save this new test.\n"
            "3. **Confirm Failure:** Use `run_tests`. You MUST analyze the output and confirm that the new test fails as expected. This is a critical step.\n"
            "4. **Formulate Fix:** Read the source code file again. In your thought, formulate a precise plan to fix the code.\n"
            "5. **Execute Fix:** Use `write_file` to overwrite the original source file with the corrected code.\n"
            "6. **Confirm Fix:** Use `run_tests` one final time. You MUST analyze the output and confirm that all tests now pass.\n"
            "7. **Finish:** Use the `finish` tool to report the successful end-to-end process. The `final_answer` argument should contain your summary.\n\n"
            "Return JSON: {\"thought\": \"...\", \"action\": {\"tool\": \"...\", \"args\": {...}}}\n\n"
            "AVAILABLE_TOOLS:\n" + self.tool_definitions + "\n"
        )


    def step(self, task: Task, persona: str = "default") -> Task:
        """
        Execute one reasoning + tool invocation step for the given Task.
        Updates `task.next_input`, `task.history`, `task.status`, and `task.final_answer` as appropriate.
        """
        if getattr(task, "status", "") != "running":
            print(f"    - Task {getattr(task, 'task_id', '<unknown>')} is not running. No action taken.")
            return task

        # Build LLM history: system prompt + reconstructed previous steps
        system_prompt = self.system_prompts.get(persona, self.system_prompts["default"])
        history_for_llm: List[Dict[str, Any]] = [{"role": "user", "parts": [system_prompt]}]

        # Accept history entries as dicts or objects
        for step_record in getattr(task, "history", []):
            if isinstance(step_record, dict):
                thought_text = step_record.get("thought", "")
                action_obj = step_record.get("action", {})
                result_text = step_record.get("result", "")
            else:
                thought_text = getattr(step_record, "thought", "")
                action_obj = getattr(step_record, "action", {})
                result_text = getattr(step_record, "result", "")

            history_for_llm.append({"role": "model", "parts": [json.dumps({"thought": thought_text, "action": action_obj})]})
            history_for_llm.append({"role": "user", "parts": [f"TOOL_RESULT:\n```\n{result_text}\n```"]})

        chat = self.llm.start_chat(history=history_for_llm)
        current_turn = len(getattr(task, "history", [])) + 1
        print(f"\n--- 🤔 Agent Turn {current_turn} ---")

        try:
            response = chat.send_message(getattr(task, "next_input", ""))
            response_text = getattr(response, "text", str(response))
            print(f"    - Raw LLM Output:\n{response_text}")

            parsed = safe_parse_json(response_text, chat=chat)
            validated = AgentResponse(**parsed)

            thought = validated.thought
            tool_call = validated.action

            print(f"    - Thought: {thought}")
            print(f"    - Action: Calling `{tool_call.tool}` with args: {tool_call.args}")

            # Finish action
            if tool_call.tool == "finish":
                print("    - ✅ Mission Complete.")
                task.status = "completed"
                task.final_answer = tool_call.args.get("final_answer", "Mission complete.")
                try:
                    task.add_step(current_turn, thought, tool_call.dict(), task.final_answer)
                except Exception:
                    pass
                return task

            # Execute tool
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
            # AgentResponse validation or JSON parsing/self-correction failure
            result = f"Error in agent response: {e}"
            print(f"    - ❌ {result}")
            task.next_input = f"RESPONSE_ERROR:\n```\n{result}\n```"
            try:
                task.add_step(current_turn, "Error handling response", {"tool": "error", "args": {}}, result)
            except Exception:
                pass

        except Exception as e:
            # Any unexpected error
            result = f"An unexpected error occurred: {e}"
            print(f"    - ❌ {result}")
            task.status = "failed"
            task.final_answer = result
            try:
                task.add_step(current_turn, "FATAL ERROR", {"tool": "error", "args": {}}, result)
            except Exception:
                pass

        return task

    def mission_loop(self, task: Task, persona: str = "default") -> Task:
        """
        Run `step` repeatedly until the task is no longer 'running'.
        After every step we persist the task with `save_task`.
        """
        while getattr(task, "status", "") == "running":
            task = self.step(task, persona=persona)
            try:
                save_task(task)
            except Exception as e:
                print(f"    - ⚠️ Failed to save task state: {e}")

        print("\n--- 🚀 Mission Loop Finished ---")
        print(f"    - Task ID: {getattr(task, 'task_id', '<unknown>')}")
        print(f"    - Final Status: {getattr(task, 'status', '<unknown>')}")
        print(f"    - Final Answer: {getattr(task, 'final_answer', '<none>')}")

        return task

