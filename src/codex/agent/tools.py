"""
Defines the suite of tools available to the AI agent.
"""

import os
import json
import subprocess
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WORKSPACE_PATH = PROJECT_ROOT / "workspace"
WORKSPACE_PATH.mkdir(exist_ok=True)

# --- Filesystem Tools ---

def list_files(directory: str = ".") -> str:
    """Lists all files and directories in the agent's sandboxed workspace."""
    try:
        full_path = (WORKSPACE_PATH / directory).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        if not full_path.is_dir():
            return f"Error: Directory '{directory}' not found."
        return json.dumps(os.listdir(full_path))
    except Exception as e:
        return f"Error listing files: {e}"

def read_file(file_path: str) -> str:
    """Reads the content of a file from the agent's sandboxed workspace."""
    try:
        full_path = (WORKSPACE_PATH / file_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        if not full_path.is_file():
            return f"Error: File '{file_path}' not found."
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(file_path: str, content: str) -> str:
    """Writes or overwrites a file in the agent's sandboxed workspace."""
    try:
        full_path = (WORKSPACE_PATH / file_path).resolve()
        if not str(full_path).startswith(str(WORKSPACE_PATH.resolve())):
            return "Error: Access denied."
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Success: File '{file_path}' has been written."
    except Exception as e:
        return f"Error writing file: {e}"

def create_new_file(relative_file_path: str, content: str) -> str:
    """Creates a new file in the agent's sandboxed workspace."""
    return write_file(relative_file_path, content)

def create_new_test_file(relative_file_path: str, content: str) -> str:
    """Creates a new test file in the 'tests/' subdirectory of the workspace."""
    # Sanitize the relative path to prevent directory traversal
    safe_filename = Path(relative_file_path).name
    full_path = WORKSPACE_PATH / "tests" / safe_filename
    
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')
        workspace_relative_path = full_path.relative_to(WORKSPACE_PATH)
        return f"Success: Test file created at '{workspace_relative_path}'."
    except Exception as e:
        return f"Error creating test file: {e}"

def run_tests() -> str:
    """
    Executes the pytest suite inside a secure Docker container, building the image
    from the clean workspace context to ensure speed and security.
    """
    image_tag = "codex-veritas-agent-runner"
    dockerfile_path = WORKSPACE_PATH / "agent.Dockerfile"

    if not dockerfile_path.exists():
        return "Error: agent.Dockerfile not found in the workspace. Cannot run tests."

    # --- DEFINITIVE FIX: The build context is now the clean WORKSPACE_PATH ---
    build_context = str(WORKSPACE_PATH)

    build_command = [
        "docker", "build",
        "-t", image_tag,
        "-f", str(dockerfile_path),
        build_context
    ]
    
    print(f"--- 🐳 Building Docker image: `{' '.join(build_command)}` ---")
    
    try:
        # Capture raw bytes and decode manually with utf-8
        build_process = subprocess.run(
            build_command,
            capture_output=True,
            check=False
        )
        if build_process.returncode != 0:
            error_output = build_process.stdout.decode('utf-8', errors='ignore') + "\n" + build_process.stderr.decode('utf-8', errors='ignore')
            return f"Docker build failed:\n{error_output}"

        run_command = ["docker", "run", "--rm", image_tag]
        
        print(f"--- 🚀 Running tests in container: `{' '.join(run_command)}` ---")
        
        run_process = subprocess.run(
            run_command,
            capture_output=True,
            check=False
        )
        
        output = run_process.stdout.decode('utf-8', errors='ignore') + "\n" + run_process.stderr.decode('utf-8', errors='ignore')
        return output

    except FileNotFoundError:
        return "Error: `docker` command not found. Is Docker installed and running?"
    except Exception as e:
        return f"An unexpected error occurred during test execution: {e}"

