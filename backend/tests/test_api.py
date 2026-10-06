import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app


def make_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    return TestClient(app)


def test_catalog_and_persistent_experiment_round_trip():
    client = make_client()
    assert client.get("/api/health").json()["status"] == "ok"
    catalog = client.get("/api/catalog").json()
    assert len(catalog["bugs"]) == 6
    assert "fixed_source" not in catalog["bugs"][0]
    response = client.post("/api/experiments", json={"name": "  Measured baseline  ", "bug_ids": ["FL-001", "FL-002"], "methods": ["ochiai", "tarantula"]})
    assert response.status_code == 201
    experiment = response.json()
    assert experiment["name"] == "Measured baseline"
    assert len(experiment["results"]) == 4
    assert experiment["summary"]["ochiai"]["cases"] == 2
    assert client.get(f'/api/experiments/{experiment["id"]}').json() == experiment
    assert client.get("/api/experiments").json()[0]["id"] == experiment["id"]
    exported = client.get(f'/api/experiments/{experiment["id"]}/export')
    assert json.loads(exported.content) == experiment
    assert "attachment" in exported.headers["content-disposition"]


def test_invalid_requests_do_not_save_runs():
    client = make_client()
    base = {"name": "Test", "bug_ids": ["FL-001"], "methods": ["ochiai"]}
    for patch in (
        {"bug_ids": ["unknown"]}, {"bug_ids": []}, {"bug_ids": ["FL-001", "FL-001"]},
        {"methods": ["llm"]}, {"methods": []}, {"methods": ["ochiai", "ochiai"]},
        {"name": " "}, {"name": "x" * 101},
    ):
        assert client.post("/api/experiments", json={**base, **patch}).status_code == 422
    assert client.get("/api/experiments").json() == []
    assert client.get("/api/experiments/missing").status_code == 404


def test_runner_timeout_returns_actionable_error_without_saving(monkeypatch):
    import subprocess
    import app.main

    def timeout(*args):
        raise subprocess.TimeoutExpired("fixture", 10)

    monkeypatch.setattr(app.main, "evaluate", timeout)
    client = make_client()
    response = client.post("/api/experiments", json={"bug_ids": ["FL-001"], "methods": ["ochiai"]})
    assert response.status_code == 504
    assert client.get("/api/experiments").json() == []


def test_jobs_enqueue_cancel_and_retry_as_new_run():
    client = make_client()
    response = client.post("/api/jobs", json={"name": "Durable run", "bug_ids": ["FL-001"], "methods": ["ochiai"]})
    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "queued"
    assert client.get(f'/api/jobs/{job["id"]}').json() == job
    assert client.get("/api/experiments").json() == []
    assert client.post(f'/api/jobs/{job["id"]}/retry').status_code == 409
    assert client.post(f'/api/jobs/{job["id"]}/cancel').json()["status"] == "cancelled"
    retry = client.post(f'/api/jobs/{job["id"]}/retry')
    assert retry.status_code == 202
    assert retry.json()["id"] != job["id"]
    assert retry.json()["attempts"] == 0
    assert len(client.get("/api/jobs").json()) == 2
    assert client.post("/api/jobs", json={"bug_ids": ["unknown"], "methods": ["ochiai"]}).status_code == 422


def test_research_endpoints_preserve_archived_outcomes():
    from app.database import ResearchImport
    client = make_client()
    for session in app.dependency_overrides[get_session]():
        session.add(ResearchImport(id="synthetic", name="Synthetic study", created_at="2026-01-01", payload={"run_count": 1, "observation_count": 2, "runs": [{"rows": [{"fn_leak": None}]}]}))
        session.commit()
    assert client.get("/api/research").json()[0]["observation_count"] == 2
    assert client.get("/api/research/synthetic").json()["runs"][0]["rows"][0]["fn_leak"] is None
    assert client.get("/api/research/missing").status_code == 404


def test_prompt_plans_persist_exact_first_step_and_export_without_inference():
    client = make_client()
    response = client.post('/api/prompt-plans', json={'bug_id': 'FL-002', 'strategy': 'chain_evidence', 'evidence_mode': 'failure_details'})
    assert response.status_code == 201
    plan = response.json()
    assert len(plan['steps']) == 3
    assert plan['status'] == 'prepared_no_inference'
    assert client.get(f'/api/prompt-plans/{plan["id"]}').json() == plan
    assert client.get('/api/prompt-plans').json()[0]['id'] == plan['id']
    assert client.get(f'/api/prompt-plans/{plan["id"]}/export').json() == plan
    assert client.get('/api/experiments').json() == []
    assert client.post('/api/prompt-plans', json={'bug_id': 'unknown', 'strategy': 'single', 'evidence_mode': 'failure_details'}).status_code == 422
    assert client.get('/api/prompt-plans/missing').status_code == 404


def test_ollama_api_freezes_shared_evidence_and_retries_as_new_snapshot(monkeypatch):
    from app import ollama_client
    monkeypatch.setattr(ollama_client, 'inventory', lambda: {'connected':True,'models':[{'name':'test-local:1b','digest':'synthetic'}], 'server_version':'test'})
    client = make_client()
    plan = client.post('/api/prompt-plans', json={'bug_id':'FL-001','strategy':'single','evidence_mode':'failure_details'}).json()
    job = client.post('/api/ollama/runs', json={'plan_id':plan['id'],'model':'test-local:1b','compare':True})
    assert job.status_code == 202
    run_id = job.json()['id']
    run = client.get(f'/api/ollama/runs/{run_id}').json()
    assert run['status'] == 'queued'
    assert len(run['plans']) == 2
    assert len({plan['evidence_sha256'] for plan in run['plans']}) == 1
    assert run['calls'] == []
    assert client.get(f'/api/ollama/runs/{run_id}/export').json() == run
    assert client.get('/api/ollama/runs').json()[0]['id'] == run_id
    client.post(f'/api/jobs/{run_id}/cancel')
    retried = client.post(f'/api/jobs/{run_id}/retry')
    assert retried.status_code == 202
    assert retried.json()['id'] != run_id
    assert client.get(f'/api/ollama/runs/{retried.json()["id"]}').json()['calls'] == []
    assert client.post('/api/ollama/runs', json={'plan_id':plan['id'],'model':'unknown'}).status_code == 422
