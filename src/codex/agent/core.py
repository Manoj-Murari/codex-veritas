"""
The Agent's Brain: The Core Reasoning and Orchestration Engine.

This module defines the `Agent` class, which is the central component of our
task-oriented AI system. It is responsible for:
1.  Initializing with all necessary tools and services (like the QueryEngine).
2.  Managing the conversational history with the LLM.
3.  Executing the main "reasoning loop":
    -   Sending the current state to the LLM to get the next "thought" and "action".
    -   Parsing and validating the LLM's response.
    -   Dispatching the requested action to the appropriate tool.
    -   Feeding the result of the tool back into the loop.
4.  Returning the final answer once the `finish` tool is called.
"""

import json
import re
import inspect
import os
from pathlib import Path
from typing import Dict, Any, List

import google.generativeai as genai
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

# --- Local Imports ---
from ..query.engine import QueryEngine
from . import tools as agent_tools

# --- Configuration & Environment Loading ---
# This is the definitive, robust way to find the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

def configure_services():
    """Initializes the connection to the Google Generative AI service."""
    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise KeyError
        genai.configure(api_key=api_key)
    except KeyError:
        print("--- ❌ ERROR: GOOGLE_API_KEY not found or is empty in your .env file. ---")
        print(f"--- Searched for .env file at: {PROJECT_ROOT / '.env'} ---")
        exit()

# Configure the API key as soon as the module is loaded.
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

class Agent:
    """The core AI agent responsible for reasoning and tool execution."""

    def __init__(self, query_engine: QueryEngine):
        """
        Initializes the agent with its tools and services.

        Args:
            query_engine: An instance of the QueryEngine for codebase analysis.
        """
        self.query_engine = query_engine
        self.llm = genai.GenerativeModel(AGENT_MODEL_NAME)
        
        self.tools = {
            "list_files": agent_tools.list_files,
            "read_file": agent_tools.read_file,
            "write_file": agent_tools.write_file,
            "query_semantic": self.query_engine.query_semantic,
            "query_structural": self.query_engine._query_structural,
        }
        
        self.tool_definitions = "\n".join([
            f"- `{name}{str(inspect.signature(func))}`: {func.__doc__.strip().splitlines()[0]}"
            for name, func in self.tools.items()
        ])
        
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Constructs the system prompt with the available tool definitions."""
        return f"""
You are an expert software engineer agent. Your goal is to complete the user's request by creating a plan and executing it using ONLY your available tools.

**RULES:**
1.  **PLAN:** First, think step-by-step to create a plan.
2.  **TOOL USE:** Execute the plan using ONLY the tools listed below. You can only use one tool at a time.
3.  **SELF-CORRECT:** If a tool returns an error, analyze the error and create a new plan to fix the problem.
4.  **RESPONSE FORMAT:** You MUST always respond with a single JSON object that validates against this Pydantic schema: `{{"thought": "...", "action": {{"tool": "...", "args": {{...}}}}}}`.
5.  **FINISH:** Once your plan is complete and you have the final answer, you MUST use the `finish` tool. This is the only way to end the mission.

**AVAILABLE TOOLS (You can ONLY use these):**
{self.tool_definitions}
- `finish(final_answer: str)`: Signals completion and provides the final answer to the user.
"""

    def run(self, task: str) -> str:
        """
        Executes the main reasoning loop for a given task.

        Args:
            task: The user's initial request.

        Returns:
            The final answer from the agent.
        """
        chat = self.llm.start_chat(history=[
            {'role': 'user', 'parts': self.system_prompt},
            {'role': 'model', 'parts': "Acknowledged. I will follow all instructions and use the provided tools to complete the user's task."}
        ])
        
        next_input = f"USER_REQUEST: {task}"
        
        for i in range(15): # Safety break to prevent infinite loops
            print(f"\n--- 🤔 Agent Turn {i+1} ---")
            
            try:
                response = chat.send_message(next_input)
                response_text = response.text
                print(f"   - Raw LLM Output:\n{response_text}")

                # Use regex to find the JSON blob, even with surrounding text
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if not json_match:
                    json_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)

                if not json_match:
                    raise ValueError("No valid JSON object found in the response.")
                
                parsed_json = json.loads(json_match.group(1))
                validated_response = AgentResponse(**parsed_json)
                
                thought = validated_response.thought
                tool_call = validated_response.action
                
                print(f"   - Thought: {thought}")
                print(f"   - Action: Calling `{tool_call.tool}` with args: {tool_call.args}")

                if tool_call.tool == "finish":
                    print("   - ✅ Mission Complete.")
                    return tool_call.args.get("final_answer", "Mission complete.")

                if tool_call.tool in self.tools:
                    tool_function = self.tools[tool_call.tool]
                    try:
                        result = tool_function(**tool_call.args)
                        next_input = f"TOOL_RESULT:\n```\n{result}\n```"
                    except Exception as e:
                        next_input = f"TOOL_ERROR:\n```\nTool {tool_call.tool} failed with error: {e}\n```"
                else:
                    next_input = f"TOOL_ERROR:\n```\nError: You tried to call an unknown tool named '{tool_call.tool}'.\n```"
            
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                print(f"   - ❌ Error in agent response: {e}")
                next_input = f"""RESPONSE_ERROR:\n```\nYour last response was not valid. Reason: {e}. You MUST respond with a valid JSON object matching the required schema.\n```"""
            
            except Exception as e:
                print(f"   - ❌ An unexpected error occurred: {e}")
                return f"An unexpected error occurred. Halting execution. Details: {e}"

        return "Agent could not reach a conclusion after multiple turns."