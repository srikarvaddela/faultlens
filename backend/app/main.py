from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import subprocess
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .catalog import BY_ID, CATALOG, public_bug
from .database import Experiment, Job, ResearchImport, PromptPlan, get_session, initialize_database
from .evaluation import METHODS, evaluate, summarize
from .jobs import enqueue, job_view
from .prompting import prepare


@asynccontextmanager
async def lifespan(app):
    initialize_database()
    yield


app = FastAPI(title="FaultLens", version="0.2.0", lifespan=lifespan)
DB = Annotated[Session, Depends(get_session)]


class RunRequest(BaseModel):
    name: str = Field(default="Baseline comparison", min_length=1, max_length=100)
    bug_ids: list[str] = Field(min_length=1, max_length=6)
    methods: list[Literal["ochiai", "tarantula"]] = Field(min_length=1, max_length=2)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        if not value.strip():
            raise ValueError("Experiment name cannot be blank")
        return value.strip()

    @field_validator("bug_ids", "methods")
    @classmethod
    def unique_values(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Selections must be unique")
        return values


class PlanRequest(BaseModel):
    bug_id: str
    strategy: Literal['single', 'chain_original', 'chain_evidence']
    evidence_mode: Literal['failure_details', 'exception_only']


@app.post('/api/prompt-plans', status_code=201)
def create_plan(request: PlanRequest, session: DB):
    if request.bug_id not in BY_ID:
        raise HTTPException(422, 'Unknown curated bug')
    try:
        payload = prepare(request.bug_id, request.strategy, request.evidence_mode)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, 'Evidence collection timed out')
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        raise HTTPException(500, 'Evidence collection failed; no plan was saved')
    session.add(PromptPlan(id=payload['id'], created_at=payload['created_at'], payload=payload))
    session.commit()
    return payload


@app.get('/api/prompt-plans')
def list_plans(session: DB):
    return [{'id': plan.id, 'created_at': plan.created_at, 'bug_id': plan.payload['bug_id'], 'strategy': plan.payload['strategy'], 'evidence_mode': plan.payload['evidence_mode'], 'prompt_version': plan.payload['prompt_version']} for plan in session.scalars(select(PromptPlan).order_by(PromptPlan.created_at.desc()).limit(100)).all()]


@app.get('/api/prompt-plans/{plan_id}')
def get_plan(plan_id: str, session: DB):
    plan = session.get(PromptPlan, plan_id)
    if not plan:
        raise HTTPException(404, 'Prompt plan not found')
    return plan.payload


@app.get('/api/prompt-plans/{plan_id}/export')
def export_plan(plan_id: str, session: DB):
    payload = get_plan(plan_id, session)
    return Response(json.dumps(payload, indent=2), media_type='application/json', headers={'Content-Disposition': f'attachment; filename="faultlens-plan-{payload["id"]}.json"'})


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/api/catalog")
def catalog():
    return {
        "bugs": [public_bug(bug) for bug in CATALOG], "methods": list(METHODS.values()),
        "dataset": {"name": "FaultLens curated v1", "kind": "Original educational fixtures", "version": "1.0.0", "cases": len(CATALOG)},
    }


@app.get("/api/experiments")
def list_experiments(session: DB):
    experiments = session.scalars(select(Experiment).order_by(Experiment.created_at.desc()).limit(100)).all()
    return [{"id": exp.id, "name": exp.name, "created_at": exp.created_at, "summary": exp.payload["summary"], "bug_ids": exp.payload["bug_ids"], "methods": exp.payload["methods"]} for exp in experiments]


@app.get("/api/research")
def list_research(session: DB):
    return [{"id": item.id, "name": item.name, "created_at": item.created_at, "run_count": item.payload["run_count"], "observation_count": item.payload["observation_count"]} for item in session.scalars(select(ResearchImport).order_by(ResearchImport.created_at.desc())).all()]


@app.get("/api/research/{import_id}")
def get_research(import_id: str, session: DB):
    item = session.get(ResearchImport, import_id)
    if not item:
        raise HTTPException(404, "Research import not found")
    return item.payload


@app.post("/api/jobs", status_code=202)
def create_job(request: RunRequest, session: DB):
    if any(bug_id not in BY_ID for bug_id in request.bug_ids):
        raise HTTPException(422, "Unknown bug ID; only packaged fixtures can run")
    return enqueue(session, request.model_dump())


@app.get("/api/jobs")
def list_jobs(session: DB):
    return [job_view(job) for job in session.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)).all()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, session: DB):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job_view(job)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, session: DB):
    # Conditional writes make completion-vs-cancellation races explicit.
    session.execute(update(Job).where(Job.id == job_id, Job.status == "queued").values(status="cancelled", cancel_requested=True))
    session.execute(update(Job).where(Job.id == job_id, Job.status == "running").values(cancel_requested=True))
    session.commit()
    return get_job(job_id, session)


@app.post("/api/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, session: DB):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status not in ("failed", "cancelled"):
        raise HTTPException(409, "Only failed or cancelled jobs can be retried")
    # A retry is a new job with its own bounded retry budget and audit trail.
    return enqueue(session, dict(job.request))


@app.post("/api/experiments", status_code=201, deprecated=True)
def create_experiment(request: RunRequest, session: DB):
    if any(bug_id not in BY_ID for bug_id in request.bug_ids):
        raise HTTPException(422, "Unknown bug ID; only packaged fixtures can run")
    try:
        results = [evaluate(BY_ID[bug_id], method) for method in request.methods for bug_id in request.bug_ids]
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Fixture evaluation timed out")
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        logging.exception("Fixture runner failed")
        raise HTTPException(500, "Fixture runner failed; no experiment was saved")
    payload = {
        "id": str(uuid4()), "name": request.name, "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "FaultLens curated v1", "dataset_version": "1.0.0", "evaluator_version": "1.1.0", "shared_evidence": False,
        "tie_policy": "worst rank within equal-score group", "bug_ids": request.bug_ids,
        "methods": request.methods, "results": results,
        "summary": {method: summarize([result for result in results if result["method"] == method]) for method in request.methods},
    }
    session.add(Experiment(id=payload["id"], name=payload["name"], created_at=payload["created_at"], payload=payload))
    session.commit()
    return payload


@app.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: str, session: DB):
    experiment = session.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(404, "Experiment not found")
    return experiment.payload


@app.get("/api/experiments/{experiment_id}/export")
def export_experiment(experiment_id: str, session: DB):
    payload = get_experiment(experiment_id, session)
    return Response(json.dumps(payload, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="faultlens-{payload["id"]}.json"'})
