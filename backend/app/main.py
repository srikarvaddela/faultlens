from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import subprocess
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import BY_ID, CATALOG, public_bug
from .database import Base, Experiment, engine, get_session
from .evaluation import METHODS, evaluate, summarize


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="FaultLens", version="0.1.0", lifespan=lifespan)
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


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


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


@app.post("/api/experiments", status_code=201)
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
        "dataset": "FaultLens curated v1", "dataset_version": "1.0.0", "evaluator_version": "1.0.0",
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
