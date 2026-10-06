import json
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, InferenceRun, Job
from app.jobs import process_one, claim
from app.ollama_runs import enqueue_run, run_owned
from app import ollama_client
from app.prompting import prepare


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path/'ollama.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def submit(factory, strategies=('single', 'chain_evidence')):
    plans = [prepare('FL-001', strategy, 'failure_details') for strategy in strategies]
    with factory() as session:
        return enqueue_run(session, plans, {'name': 'test-local:1b', 'digest': 'synthetic-digest'}, 'test-version')['id']


def inventory():
    return {'models': [{'name': 'test-local:1b', 'digest': 'synthetic-digest'}], 'server_version': 'test-version'}


def reply(payload):
    content = json.dumps({'candidates': [{'line': 3, 'reason': 'Percent is not divided by 100'}]}) if 'format' in payload else 'Analysis of the discount scale.'
    return {'done': True, 'done_reason': 'stop', 'model': payload['model'], 'message': {'role': 'assistant', 'content': content}, 'prompt_eval_count': 100, 'eval_count': 20, 'total_duration': 1000000}


def test_exact_calls_saved_before_inference_and_chain_context_uses_real_responses(factory, monkeypatch):
    run_id = submit(factory)
    monkeypatch.setattr(ollama_client, 'inventory', inventory)
    seen = []

    def fake_chat(payload):
        with factory() as session:
            saved = session.get(InferenceRun, run_id).payload['calls'][-1]
            assert saved['request_payload'] == payload
            assert saved['status'] == 'request_saved'
        seen.append(payload)
        return reply(payload)

    monkeypatch.setattr(ollama_client, 'chat', fake_chat)
    assert process_one(factory)
    with factory() as session:
        assert session.get(Job, run_id).status == 'completed'
        payload = session.get(InferenceRun, run_id).payload
        assert len(payload['calls']) == 4
        assert len(payload['results']) == 2
        assert all(result['top1'] for result in payload['results'])
        assert all(call['response_sha256'] for call in payload['calls'])
    assert seen[0]['format']
    assert 'format' not in seen[1]
    assert 'Analysis of the discount scale.' in seen[2]['messages'][1]['content']
    assert 'Analysis of the discount scale.' in seen[3]['messages'][1]['content']


def test_provider_failure_is_retained_without_automatic_replay(factory, monkeypatch):
    run_id = submit(factory, ('single',))
    monkeypatch.setattr(ollama_client, 'inventory', inventory)

    def fail(payload):
        raise ollama_client.OllamaError('Test timeout')

    monkeypatch.setattr(ollama_client, 'chat', fail)
    process_one(factory)
    assert not process_one(factory)
    with factory() as session:
        assert session.get(Job, run_id).status == 'failed'
        assert session.get(InferenceRun, run_id).payload['error'] == 'Test timeout'
        assert session.get(InferenceRun, run_id).payload['calls'][0]['response'] is None


def test_changed_model_digest_prevents_inference(factory, monkeypatch):
    run_id = submit(factory)
    monkeypatch.setattr(ollama_client, 'inventory', lambda: {'models': [{'name':'test-local:1b','digest':'changed'}]})
    monkeypatch.setattr(ollama_client, 'chat', lambda _: pytest.fail('must not call model'))
    process_one(factory)
    with factory() as session:
        assert session.get(Job, run_id).status == 'failed'
        assert session.get(InferenceRun, run_id).payload['calls'] == []


def test_server_version_change_prevents_mixed_runtime_calls(factory, monkeypatch):
    run_id = submit(factory)
    replies = iter([inventory(), {**inventory(), 'server_version': 'changed-version'}])
    monkeypatch.setattr(ollama_client, 'inventory', lambda: next(replies))
    monkeypatch.setattr(ollama_client, 'chat', lambda _: pytest.fail('must not call changed runtime'))
    process_one(factory)
    with factory() as session:
        assert session.get(Job, run_id).status == 'failed'
        assert session.get(InferenceRun, run_id).payload['calls'] == []


def test_reclaimed_worker_does_not_reissue_uncertain_calls(factory, monkeypatch):
    run_id = submit(factory)
    assert claim(factory, now=time.time()-120)
    monkeypatch.setattr(ollama_client, 'chat', lambda _: pytest.fail('must not replay'))
    process_one(factory)
    with factory() as session:
        assert session.get(Job, run_id).status == 'failed'
        assert 'Worker restarted' in session.get(InferenceRun, run_id).payload['error']


def test_cancellation_between_calls_preserves_response_and_stops_next_call(factory, monkeypatch):
    run_id = submit(factory)
    monkeypatch.setattr(ollama_client, 'inventory', inventory)

    def cancel(payload):
        with factory() as session:
            session.get(Job, run_id).cancel_requested = True
            session.commit()
        return reply(payload)

    monkeypatch.setattr(ollama_client, 'chat', cancel)
    process_one(factory)
    with factory() as session:
        assert session.get(Job, run_id).status == 'cancelled'
        assert len(session.get(InferenceRun, run_id).payload['calls']) == 1
        assert session.get(InferenceRun, run_id).payload['calls'][0]['response'] is not None


def test_parse_failure_is_a_visible_result(factory, monkeypatch):
    run_id = submit(factory, ('single',))
    monkeypatch.setattr(ollama_client, 'inventory', inventory)
    monkeypatch.setattr(ollama_client, 'chat', lambda payload: {**reply(payload), 'message': {'content': 'invalid json'}})
    process_one(factory)
    with factory() as session:
        result = session.get(InferenceRun, run_id).payload['results'][0]
        assert result['parse']['valid'] is False
        assert result['parse']['error'] == 'invalid_json'


def test_external_hosts_and_redirect_urls_are_rejected(monkeypatch):
    for value in ('https://example.com', 'http://example.com', 'http://localhost:11434/api', 'http://user:pass@localhost:11434'):
        monkeypatch.setenv('OLLAMA_BASE_URL', value)
        with pytest.raises(ollama_client.OllamaError):
            ollama_client.base_url()


def test_cloud_models_are_not_offered(monkeypatch):
    monkeypatch.setattr(ollama_client, 'request', lambda path: {'version': 'test'} if path == '/api/version' else {'models': [{'name':'local:1b','digest':'localhash'}, {'name':'remote-cloud','digest':'remotehash'}, {'name':'alias','digest':'alias','remote_model':'cloud-model'}]})
    assert [model['name'] for model in ollama_client.inventory()['models']] == ['local:1b']
