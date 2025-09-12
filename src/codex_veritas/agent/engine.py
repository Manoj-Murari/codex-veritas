# src/codex_veritas/agent/engine.py

"""
The core logic for the Codex Veritas agentic engine.

This module contains the primary components that drive the AI's reasoning and
tool-use capabilities. It includes:
- EngineServices: A singleton class to manage connections to external services
  like ChromaDB and the generative AI models.
- QueryClassification: Pydantic models to enforce structured output from the AI.
- classify_query: A function to determine the user's intent.
- run_agentic_flow: The main loop that handles multi-step reasoning, tool execution,
  and self-correction.
- answer_query: The main entry point that routes the user's question to the
  appropriate handler.
"""

import os
import json
import re
import google.generativeai as genai
import chromadb
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, List, Dict, Generator, Union

# --- Local Imports ---
from .tools import (
    read_file, list_files, create_file, update_file, delete_file,
    list_workspace_files, read_workspace_file, query_code_graph, finish
)

# --- Configuration & Environment Loading ---
# Navigate four levels up from this file's location (src/codex_veritas/agent/engine.py) to the project root.
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

def configure_services():
    """Initializes the connection to the Google Generative AI service."""
    try:
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    except KeyError:
        print("--- ❌ ERROR: GOOGLE_API_KEY not found. Please create a .env file in the project root. ---")
        exit()

# --- Constants ---
AGENT_MODEL_NAME = "gemini-1.5-pro-latest"
CLASSIFICATION_MODEL_NAME = "gemini-1.5-flash"
CHROMA_DB_PATH = PROJECT_ROOT / "code_db"
# --- This now matches the default in cli.py ---
COLLECTION_NAME = "code_embeddings"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Pydantic Models for Structured Output ---
class QueryClassification(BaseModel):
    """A Pydantic model to validate the output of the query classifier."""
    query_type: Literal["DEFINITION", "FLOW", "ARCHITECTURE", "AGENT"] = Field(description="The category of the user's query.")
    target_entity: str = Field(description="The main code entity (function, class, file) the user is asking about. N/A if not applicable.")

# --- Singleton Class for Service Management ---
class EngineServices:
    """Manages shared resources like database connections as a singleton."""
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            print("--- Initializing Engine Services (Singleton) ---")
            cls._instance = super(EngineServices, cls).__new__(cls)
            configure_services()
            try:
                from chromadb.utils import embedding_functions
                sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
                client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
                # --- This will now correctly find the collection created by the `analyze` command ---
                cls._instance.collection = client.get_collection(name=COLLECTION_NAME, embedding_function=sentence_transformer_ef)
                print(f"--- ✅ Successfully connected to ChromaDB collection '{COLLECTION_NAME}'. ---")
            except Exception as e:
                print(f"--- ❌ ERROR: Could not connect to ChromaDB. Have you run `codex analyze`? Error: {e} ---")
                cls._instance.collection = None # Ensure it's None on failure
        return cls._instance

# --- Core AI Functions ---

def classify_query(query: str, chat_history: List[Dict]) -> QueryClassification:
    """
    Uses a smaller, faster model to classify the user's query into a specific category.
    This helps route the query to the most efficient handler.
    """
    print(f"--- 🧠 Classifying query: '{query}'... ---")
    model = genai.GenerativeModel(CLASSIFICATION_MODEL_NAME)
    
    # --- The prompt is now much stricter to prevent validation errors. ---
    prompt = f"""
    You are an expert query classifier. Your task is to analyze a user's query about a codebase and classify it.
    You MUST respond with a valid JSON object that strictly follows this format: {{"query_type": "...", "target_entity": "..."}}. Do not add any other text or explanation.

    **Category Definitions:**
    - `AGENT`: For queries requiring actions like creating, updating, reading, or listing files, or for complex questions that require multi-step reasoning or investigation. This is the default for commands or vague questions.
    - `DEFINITION`: For queries asking for the definition or content of a single, specific, named code entity.
    - `FLOW`: For "how-to" questions about a process that involves multiple components.
    - `ARCHITECTURE`: For high-level questions about project structure or design patterns.

    **Chat History (for context):**
    {json.dumps(chat_history, indent=2)}

    **User's Latest Query:**
    "{query}"
    """
    try:
        response = model.generate_content(prompt, generation_config=genai.GenerationConfig(response_mime_type="application/json"))
        parsed_json = json.loads(response.text)
        return QueryClassification(**parsed_json)
    except (ValidationError, json.JSONDecodeError, Exception) as e:
        print(f"--- ⚠️ Warning: Classifier failed, defaulting to AGENT. Error: {e} ---")
        return QueryClassification(query_type="AGENT", target_entity="N/A")

def run_agentic_flow(query: str, chat_history: List[Dict], services: EngineServices) -> Generator[Dict, None, None]:
    """
    Executes the main agentic loop for complex, multi-step tasks.
    The agent thinks, chooses a tool, executes it, and repeats until the task is complete.
    """
    print(f"--- 🤖 Activating Agentic Flow for: '{query}'... ---")
    
    # --- The system prompt is much stricter to prevent hallucinating tools like 'print'. ---
    system_prompt = f"""
You are an expert software engineer agent. Your goal is to complete the user's request by creating a plan and executing it using ONLY your available tools.

**RULES:**
1.  **PLAN:** First, think step-by-step to create a plan.
2.  **TOOL USE:** Execute the plan using ONLY the tools listed below. You can only use one tool at a time.
3.  **SELF-CORRECT:** If a tool returns an error, analyze the error and create a new plan to fix the problem.
4.  **RESPONSE FORMAT:** You MUST always respond with a single JSON object containing "thought" and "action". The "action" object MUST contain "tool" and "args".
5.  **FINISH:** Once your plan is complete and you have the final answer, you MUST use the `finish` tool.

**AVAILABLE TOOLS (You can ONLY use these):**
- `read_file(file_path: str)`: Reads a file from the main code repository.
- `list_files(directory_path: str)`: Lists directory contents in the main repository.
- `read_workspace_file(file_path: str)`: Reads a file from the secure WORKSPACE.
- `list_workspace_files(directory_path: str)`: Lists directory contents in the WORKSPACE.
- `create_file(file_path: str, content: str)`: Creates a file in the workspace.
- `update_file(file_path: str, content: str)`: Updates (overwrites) a file in the workspace.
- `delete_file(file_path: str)`: Deletes a file from the workspace.
- `query_code_graph(entity_name: str, relationship: Literal['callers', 'callees'])`: Queries the code's structure.
- `finish(final_answer: str)`: Signals completion and provides the final answer to the user.
"""
    
    model = genai.GenerativeModel(AGENT_MODEL_NAME, system_instruction=system_prompt)
    
    history_for_model = [{'role': turn['role'], 'parts': turn['parts']} for turn in chat_history]
    chat = model.start_chat(history=history_for_model)
    
    available_tools = { 
        "read_file": read_file, "list_files": list_files, "create_file": create_file,
        "update_file": update_file, "delete_file": delete_file, "list_workspace_files": list_workspace_files,
        "read_workspace_file": read_workspace_file, "query_code_graph": query_code_graph, "finish": finish
    }
    
    next_input = query
    # Limit the number of turns to prevent infinite loops
    for i in range(15):
        print(f"\n--- Agent Turn {i+1} ---")
        try:
            response = chat.send_message(next_input)
            response_text = response.text
            print(f"   - Agent Raw Output:\n{response_text}")

            # Use regex to reliably extract JSON from the agent's response, even with surrounding text.
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if not json_match:
                json_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)

            if not json_match:
                raise ValueError("No valid JSON object found in the agent's response.")
            
            json_str = json_match.group(1)
            parsed_json = json.loads(json_str)

            thought = parsed_json.get("thought", "(No thought provided)")
            action = parsed_json.get("action")
            
            yield {"type": "thought", "content": thought}
            print(f"   - Agent Thought: {thought}")
            
            if not action or "tool" not in action or "args" not in action:
                 raise ValueError("Agent action is malformed or missing 'tool' or 'args'.")

            tool_name = action["tool"]
            args = action["args"]
            
            if tool_name in available_tools:
                print(f"   - ⚡ Executing Action: {tool_name}({args})")
                tool_function = available_tools[tool_name]
                tool_result = tool_function(**args)
                
                if tool_name == 'finish':
                    print("   - ✅ Agent finished. Returning final answer.")
                    yield {"type": "final_answer", "content": tool_result}
                    return
                    
                next_input = f"Tool Result for {tool_name}({args}):\n```\n{tool_result}\n```"
                continue
            else:
                # This will catch hallucinations like the 'print' tool
                raise ValueError(f"Agent requested an unknown tool: '{tool_name}'.")

        except (json.JSONDecodeError, ValueError, Exception) as e:
            error_message = f"Error parsing agent's response or executing action: {e}"
            print(f"   - ❌ {error_message}")
            yield {"type": "final_answer", "content": f"I encountered an internal error and have to stop: {e}. Please try rephrasing your request."}
            return
            
    yield {"type": "final_answer", "content": "I could not reach a conclusion after multiple turns. Please try again."}

# --- Main Query Router ---
def answer_query(question: str, chat_history: List[Dict]) -> Union[Generator[Dict, None, None], Dict]:
    """
    The main entry point for processing a user's question.
    It classifies the query and then routes it to the appropriate handler.
    """
    services = EngineServices()
    classification = classify_query(question, chat_history)
    
    print(f"\n{'='*50}\n✅ QUERY ANALYSIS COMPLETE\n{'='*50}")
    print(f"   - Query Type: {classification.query_type}\n   - Target Entity: {classification.target_entity}")
    print(f"{'='*50}\n")
    
    if classification.query_type == "AGENT":
        return run_agentic_flow(question, chat_history, services)
    
    # Non-agentic flows would be implemented here (e.g., direct RAG lookup)
    # For now, we return a simple response wrapped in a generator to match the stream format.
    def non_agent_stream():
        yield {"type": "final_answer", "content": "I can only handle agentic tasks right now. Please ask me to create, read, or analyze files."}
    
    return non_agent_stream()

