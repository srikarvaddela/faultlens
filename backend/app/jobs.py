"""Database-backed queue with conditional claims and fenced publication."""
from datetime import datetime, timezone
import json
import logging
import subprocess
import time
from uuid import uuid4

from sqlalchemy import and_, or_, select, update

from .catalog import BY_ID
from .database import Experiment, Job
from .evaluation import evaluate_methods, summarize

MAX_ATTEMPTS = 3
LEASE_SECONDS = 60  # Runner timeout is 10 seconds; renewed between each case.


def job_view(job):
    return {
        "id": job.id, "name": job.name, "created_at": job.created_at,
        "status": job.status, "attempts": job.attempts, "max_attempts": MAX_ATTEMPTS,
        "progress": job.progress, "total": len(job.request["bug_ids"]),
        "cancel_requested": job.cancel_requested, "last_error": job.last_error,
        "experiment_id": job.id if job.status == "completed" else None,
    }


def enqueue(session, request):
    job = Job(id=str(uuid4()), name=request["name"], created_at=datetime.now(timezone.utc).isoformat(), request=request)
    session.add(job)
    session.commit()
    return job_view(job)


def claim(factory, now=None):
    now = time.time() if now is None else now
    with factory() as session:
        expired = and_(Job.status == "running", Job.lease_until < now)
        session.execute(update(Job).where(expired, Job.cancel_requested.is_(True)).values(status="cancelled", lease_token=None))
        session.execute(update(Job).where(expired, Job.attempts >= MAX_ATTEMPTS).values(status="failed", lease_token=None, last_error="Worker lease expired; retry budget exhausted"))
        eligible = and_(
            or_(Job.status == "queued", expired),
            Job.attempts < MAX_ATTEMPTS, Job.cancel_requested.is_(False),
        )
        ids = session.scalars(select(Job.id).where(eligible).order_by(Job.created_at).limit(10)).all()
        for job_id in ids:
            token = str(uuid4())
            changed = session.execute(update(Job).where(Job.id == job_id, eligible).values(
                status="running", lease_token=token, lease_until=now + LEASE_SECONDS,
                attempts=Job.attempts + 1, progress=0,
            ))
            if changed.rowcount:
                session.commit()
                job = session.get(Job, job_id)
                return job_id, token, job.request
        session.commit()
    return None


def owned(job_id, token):
    return and_(Job.id == job_id, Job.status == "running", Job.lease_token == token, Job.lease_until >= time.time())


def heartbeat(factory, job_id, token, progress):
    with factory() as session:
        changed = session.execute(update(Job).where(owned(job_id, token), Job.cancel_requested.is_(False)).values(
            progress=progress, lease_until=time.time() + LEASE_SECONDS,
        ))
        if changed.rowcount:
            session.commit()
            return True
        # Cancellation only affects the matching lease; stale workers cannot mutate a new claim.
        session.execute(update(Job).where(owned(job_id, token), Job.cancel_requested.is_(True)).values(status="cancelled", lease_token=None))
        session.commit()
        return False


def publish(factory, job_id, token, request, results):
    with factory() as session:
        changed = session.execute(update(Job).where(owned(job_id, token), Job.cancel_requested.is_(False)).values(
            status="completed", lease_token=None, progress=len(request["bug_ids"]), last_error=None,
        ))
        if not changed.rowcount:
            session.rollback()
            return False
        payload = {
            "id": job_id, "name": request["name"], "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset": "FaultLens curated v1", "dataset_version": "1.0.0", "evaluator_version": "1.1.0",
            "tie_policy": "worst rank within equal-score group", "bug_ids": request["bug_ids"],
            "methods": request["methods"], "results": results, "shared_evidence": True,
            "summary": {method: summarize([result for result in results if result["method"] == method]) for method in request["methods"]},
        }
        session.add(Experiment(id=job_id, name=payload["name"], created_at=payload["created_at"], payload=payload))
        session.commit()  # Completion and result publication are one transaction.
        return True


def fail(factory, job_id, token, error):
    with factory() as session:
        job = session.scalar(select(Job).where(owned(job_id, token)))
        if not job:
            return
        status = "cancelled" if job.cancel_requested else "queued" if job.attempts < MAX_ATTEMPTS else "failed"
        session.execute(update(Job).where(owned(job_id, token)).values(
            status=status, lease_token=None, last_error=error,
        ))
        session.commit()


def process_one(factory):
    item = claim(factory)
    if not item:
        return False
    job_id, token, request = item
    results = []
    try:
        for index, bug_id in enumerate(request["bug_ids"]):
            if not heartbeat(factory, job_id, token, index):
                return True
            results.extend(evaluate_methods(BY_ID[bug_id], request["methods"]))
        if heartbeat(factory, job_id, token, len(request["bug_ids"])):
            if not publish(factory, job_id, token, request, results):
                heartbeat(factory, job_id, token, len(request["bug_ids"]))
    except subprocess.TimeoutExpired:
        fail(factory, job_id, token, "Fixture execution timed out")
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        fail(factory, job_id, token, "Fixture runner failed")
    except Exception:
        logging.exception("Job %s failed", job_id)
        fail(factory, job_id, token, "Evaluation failed; see worker logs")
    return True
