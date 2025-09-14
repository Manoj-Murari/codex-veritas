"""
The Backend Worker: The Engine Room of the Web App.

This module contains the core logic for the analysis pipeline when triggered
from the web application. It is designed to be run in the background so that it
doesn't block the web server.

The primary function, `run_full_pipeline`, orchestrates the entire process:
1. Creates a unique, isolated directory for the analysis job.
2. Clones the user-specified public GitHub repository.
3. Calls our existing, battle-tested ingestion and report generation
   modules from Sprints 1, 2, and 3.
4. Manages the status of the job in a simple, in-memory dictionary.
5. Cleans up the temporary directory after the analysis is complete.
"""

import shutil
import uuid
import stat
import os
from pathlib import Path

from git import Repo

# --- Local Imports ---
from ..ingestion.main import parse as run_ingestion
from ..report.generator import generate_report
from ..graph.core import CodeGraph

# --- In-Memory Job Status Tracking ---
JOB_STATUSES = {}

# --- Configuration ---
# --- FIXED HERE: The worker now calculates the project root itself ---
# This guarantees it creates files in the same location the API expects.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WORK_DIR = PROJECT_ROOT / "work_area"
REPORTS_DIR = PROJECT_ROOT / "reports" # This can be used in a future sprint
WORK_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


# --- Robust Cleanup Helper ---
def _on_rm_error(func, path, exc_info):
    """
    Error handler for shutil.rmtree.
    If a file is read-only, it changes permissions and retries.
    This is a common issue with .git files on Windows.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)

# --- Main Pipeline Function ---
def run_full_pipeline(job_id: str, git_url: str):
    """
    The main function that executes the entire analysis pipeline in the background.
    """
    job_dir = WORK_DIR / job_id
    repo_path = job_dir / "repo"
    graph_path = job_dir / "code_graph.json"
    
    # --- The final report is now also saved in the job-specific work directory ---
    report_path = job_dir / "codebase_guide.md" 

    try:
        JOB_STATUSES[job_id] = {"status": "running", "step": "Cloning repository..."}
        if job_dir.exists():
            shutil.rmtree(job_dir, onerror=_on_rm_error)
        job_dir.mkdir()
        
        Repo.clone_from(git_url, repo_path, depth=1)

        JOB_STATUSES[job_id]["step"] = "Tier 1: Building structural code graph..."
        run_ingestion(repo_path=repo_path, output_file=graph_path)

        JOB_STATUSES[job_id]["step"] = "Tier 3: Generating codebase guide..."
        graph = CodeGraph()
        graph.load_from_json(graph_path)
        report_content = generate_report(graph)
        
        report_path.write_text(report_content, encoding="utf-8")

        JOB_STATUSES[job_id].update({
            "status": "complete",
            "step": "Analysis complete!",
            # --- The worker now stores the path to the original graph for the API ---
            "result_graph_path": str(graph_path),
            "result_report_path": str(report_path),
        })

    except Exception as e:
        JOB_STATUSES[job_id].update({
            "status": "failed",
            "step": f"An error occurred: {str(e)}"
        })
        print(f"Job {job_id} failed: {e}")

    # Note: We are no longer cleaning up the job_dir immediately.
    # The API needs the files to exist to serve details.
    # A real production system would have a separate cleanup process.

