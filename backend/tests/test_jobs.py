import subprocess
import time

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, Job, Experiment
from app.jobs import claim, enqueue, heartbeat, process_one, publish
import app.jobs as jobs
from app.evaluation import evaluate_methods
from app.catalog import CATALOG


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'queue.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def submit(factory):
    with factory() as session:
        return enqueue(session, {"name": "Queue test", "bug_ids": ["FL-001", "FL-002"], "methods": ["ochiai", "tarantula"]})


def state(factory, job_id):
    with factory() as session:
        return session.get(Job, job_id).status


def test_queue_persists_and_publishes_one_complete_experiment(factory):
    job = submit(factory)
    assert state(factory, job["id"]) == "queued"
    assert process_one(factory)
    assert state(factory, job["id"]) == "completed"
    assert not process_one(factory)
    with factory() as session:
        experiments = session.scalars(select(Experiment)).all()
        assert len(experiments) == 1
        results = experiments[0].payload["results"]
        assert len(results) == 4
        assert results[0]["tests"] == results[1]["tests"]
        assert experiments[0].payload["shared_evidence"]


def test_only_one_worker_claims_a_live_job(factory):
    submit(factory)
    assert claim(factory) is not None
    assert claim(factory) is None


def test_expired_worker_cannot_publish_or_renew_reclaimed_job(factory):
    job = submit(factory)
    old_id, old_token, request = claim(factory, now=time.time() - 120)
    new_id, new_token, _ = claim(factory)
    assert new_id == old_id == job["id"]
    assert new_token != old_token
    assert not heartbeat(factory, old_id, old_token, 1)
    assert not publish(factory, old_id, old_token, request, [])
    with factory() as session:
        assert session.get(Job, job["id"]).attempts == 2
        assert session.get(Experiment, job["id"]) is None


def test_timeouts_exhaust_budget_without_publishing(factory, monkeypatch):
    job = submit(factory)

    def timeout(*args):
        raise subprocess.TimeoutExpired("fixture", 10)

    monkeypatch.setattr(jobs, "evaluate_methods", timeout)
    for expected in ("queued", "queued", "failed"):
        assert process_one(factory)
        assert state(factory, job["id"]) == expected
    assert not process_one(factory)
    with factory() as session:
        assert session.get(Job, job["id"]).attempts == 3
        assert session.get(Experiment, job["id"]) is None


def test_running_cancellation_prevents_publication(factory, monkeypatch):
    job = submit(factory)
    real = jobs.evaluate_methods

    def cancel_during_case(*args):
        with factory() as session:
            row = session.get(Job, job["id"])
            row.cancel_requested = True
            session.commit()
        return real(*args)

    monkeypatch.setattr(jobs, "evaluate_methods", cancel_during_case)
    process_one(factory)
    assert state(factory, job["id"]) == "cancelled"
    with factory() as session:
        assert session.get(Experiment, job["id"]) is None


def test_crashed_workers_exhaust_recovery_budget(factory):
    job = submit(factory)
    clock = time.time() - 1000
    for offset in (0, 61, 122):
        assert claim(factory, now=clock + offset)
    assert claim(factory) is None
    assert state(factory, job["id"]) == "failed"


def test_concurrent_workers_cannot_double_claim(factory):
    from concurrent.futures import ThreadPoolExecutor
    submit(factory)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim(factory), range(2)))
    assert sum(item is not None for item in claims) == 1


def test_shared_evidence_collects_tests_only_once(monkeypatch):
    import app.evaluation as evaluation
    real = evaluation.execute_tests
    calls = []

    def counted(bug):
        calls.append(bug["id"])
        return real(bug)

    monkeypatch.setattr(evaluation, "execute_tests", counted)
    results = evaluate_methods(CATALOG[0], ["ochiai", "tarantula"])
    assert len(calls) == 1
    assert results[0]["tests"] == results[1]["tests"]
    assert results[0]["evidence_duration_ms"] == results[1]["evidence_duration_ms"]
