from __future__ import annotations

import uuid
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from domain.models import BatchBrief, JobState, JobStatus
from infrastructure.persistence.in_memory_job_store import InMemoryJobStore
from infrastructure.wordpress.client import WordPressClient
from usecases.create_drafts import LLMOrchestrator
from usecases.run_batch_job import run_batch_job

app = FastAPI()
templates = Jinja2Templates(directory="templates")
job_store = InMemoryJobStore()

# Orchestrator はアプリ起動時にセットすることを想定
_orchestrator: Optional[LLMOrchestrator] = None


def configure_orchestrator(orchestrator: LLMOrchestrator) -> None:
    global _orchestrator
    _orchestrator = orchestrator


def get_orchestrator() -> LLMOrchestrator:
    if _orchestrator is None:
        raise RuntimeError("LLMOrchestrator is not configured. Call configure_orchestrator() at startup.")
    return _orchestrator


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("pages/index.html", {"request": request})


@app.post("/run", response_class=HTMLResponse)
async def run_job(
    request: Request,
    background_tasks: BackgroundTasks,
    wordpress_url: str = Form(...),
    wordpress_username: str = Form(...),
    wordpress_app_password: str = Form(...),
    topic: str = Form(...),
    main_kw: str = Form(""),
    sub_kw: str = Form(""),
    desired_count: int = Form(10),
):
    job_id = str(uuid.uuid4())
    constraints = {
        "main_keyword": main_kw,
        "sub_keywords": [kw.strip() for kw in sub_kw.split(",") if kw.strip()],
    }
    batch_brief = BatchBrief(
        topic=topic,
        target_site=wordpress_url,
        desired_count=desired_count,
        constraints=constraints,
    )

    job = JobState(job_id=job_id, status=JobStatus.queued, total=desired_count, current=0, logs=[], results=[])
    job_store.create(job)

    background_tasks.add_task(
        run_batch_job,
        job_id,
        batch_brief,
        wordpress_url,
        wordpress_username,
        wordpress_app_password,
        job_store,
        get_orchestrator,
    )

    return templates.TemplateResponse("partials/progress.html", {"request": request, "job": job})


@app.get("/progress/{job_id}", response_class=HTMLResponse)
def progress(job_id: str, request: Request):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse("partials/progress.html", {"request": request, "job": job})


@app.get("/result/{job_id}", response_class=HTMLResponse)
def result(job_id: str, request: Request):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse("partials/result.html", {"request": request, "job": job})
