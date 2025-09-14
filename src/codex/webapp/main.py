"""
The FastAPI Web Server: The Control Panel for the Web App.

This module provides the main web interface for Codex Veritas. It uses the
FastAPI framework to create a simple, modern, and asynchronous API.

It is responsible for:
1. Serving the main HTML landing page (`index.html`).
2. Serving the new, interactive report page (`report.html`).
3. Including the dedicated Data API router for all JSON-based data endpoints.
4. Providing the endpoints to start and check the status of analysis jobs.
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import markdown2

# --- Local Imports ---
from . import worker
# --- New Import for Sprint 5 ---
from . import api as data_api

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Codex Veritas",
    description="The Code Cartographer Web Application"
)

# --- Include the Data API Router ---
# This line is crucial. It tells our main application to include all the
# endpoints (`/api/report`, `/api/node`, etc.) that we defined in `api.py`.
app.include_router(data_api.router)


# --- Configuration for Templates and Static Files ---
webapp_dir = Path(__file__).parent
templates = Jinja2Templates(directory=webapp_dir / "templates")
app.mount("/static", StaticFiles(directory=webapp_dir / "static"), name="static")


# --- Main Page Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main landing page (`index.html`)."""
    return templates.TemplateResponse("index.html", {"request": request})

# --- UPDATED FOR SPRINT 5 ---
@app.get("/report/{job_id}", response_class=HTMLResponse)
async def get_report_page(request: Request, job_id: str):
    """
    Serves the new, interactive report page (`report.html`).
    The actual data will be fetched by the JavaScript on that page.
    """
    # We pass the job_id to the template so the JavaScript can access it.
    return templates.TemplateResponse("report.html", {"request": request, "job_id": job_id})


# --- Job Management Endpoints (Unchanged from Sprint 4) ---

@app.post("/analyze", response_class=JSONResponse)
async def start_analysis(request: Request, background_tasks: BackgroundTasks):
    """
    Starts a new analysis job in the background for a given GitHub URL.
    """
    data = await request.json()
    git_url = data.get("git_url")

    if not git_url:
        raise HTTPException(status_code=400, detail="git_url is required.")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(worker.run_full_pipeline, job_id, git_url)
    return {"job_id": job_id}

@app.get("/status/{job_id}", response_class=JSONResponse)
async def get_status(job_id: str):
    """
    Allows the front-end to poll for the status of an ongoing analysis job.
    """
    status = worker.JOB_STATUSES.get(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found.")
    return status

