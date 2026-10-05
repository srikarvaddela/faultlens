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
