"""
The Data API: The Nervous System of the Interactive Report.

This module provides a dedicated set of FastAPI endpoints to serve structured
JSON data to the front-end. This decouples the data-serving logic from the main
web server, creating a more robust and scalable architecture.

The API is responsible for:
1. Loading the correct CodeGraph for a given analysis job.
2. Serving the high-level report data (summary, key components).
3. Serving detailed information for a specific node in the graph, including
   its source code snippet.
4. Serving the relationships (callers and callees) for a specific node.
"""

from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# --- Local Imports ---
from ..graph.core import CodeGraph
from ..report.ranking import rank_nodes_by_centrality

# --- API Router Initialization ---
router = APIRouter(
    prefix="/api",
    tags=["Analysis Data"]
)

# --- Configuration ---
# --- FIXED HERE: The API now calculates the project root itself ---
# This guarantees it looks in the correct location for the worker's output files.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WORK_DIR = PROJECT_ROOT / "work_area"
WORK_DIR.mkdir(exist_ok=True)


# --- Pydantic Models for API Responses ---
class Node(BaseModel):
    id: str
    name: str
    type: str
    file_path: str
    start_line: int
    end_line: int
    rank: float | None = None

class ReportSummary(BaseModel):
    total_files: int
    total_components: int
    total_relations: int

class ReportData(BaseModel):
    summary: ReportSummary
    key_components: List[Node]

class NodeDetail(Node):
    source_code: str

class NodeRelations(BaseModel):
    callers: List[Node]
    callees: List[Node]


# --- Helper Function to Load Graph ---
def _get_graph_for_job(job_id: str) -> CodeGraph:
    """Loads the CodeGraph for a specific job_id."""
    graph_path = WORK_DIR / job_id / "code_graph.json"
    
    if not graph_path.exists():
        raise HTTPException(status_code=404, detail=f"Code graph for job '{job_id}' not found at {graph_path}.")
    
    graph = CodeGraph()
    graph.load_from_json(graph_path)
    return graph

# --- API Endpoints ---

@router.get("/report/{job_id}", response_model=ReportData)
async def get_report_data(job_id: str):
    """Serves the main data for the interactive report page."""
    graph = _get_graph_for_job(job_id)
    
    key_components_data = rank_nodes_by_centrality(graph, top_n=20)
    
    summary_data = {
        "total_files": len(set(n.get('file_path') for _, n in graph.graph.nodes(data=True) if n.get('file_path'))),
        "total_components": len(graph.graph.nodes),
        "total_relations": len(graph.graph.edges),
    }

    return {
        "summary": summary_data,
        "key_components": key_components_data,
    }

@router.get("/node/{job_id}/{node_id:path}", response_model=NodeDetail)
async def get_node_details(job_id: str, node_id: str):
    """Serves detailed information for a single node."""
    graph = _get_graph_for_job(job_id)
    node_data = graph.graph.nodes.get(node_id)

    if not node_data:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in graph.")

    source_code = "Source code not available."
    file_path_str = node_data.get("file_path")
    start_line = node_data.get("start_line", 0)
    end_line = node_data.get("end_line", 0)

    repo_path = WORK_DIR / job_id / "repo"
    
    if file_path_str and (repo_path / file_path_str).exists():
        try:
            with open(repo_path / file_path_str, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            snippet_lines = lines[max(0, start_line - 1):end_line]
            source_code = "".join(snippet_lines)
        except Exception as e:
            source_code = f"Error reading source file: {e}"

    return {**node_data, "id": node_id, "source_code": source_code}


@router.get("/relations/{job_id}/{node_id:path}", response_model=NodeRelations)
async def get_node_relations(job_id: str, node_id: str):
    """Serves the direct relationships for a given node."""
    graph = _get_graph_for_job(job_id)
    
    if not graph.graph.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in graph.")

    callers = graph.get_callers(node_id)
    callees = graph.get_callees(node_id)

    return {"callers": callers, "callees": callees}

