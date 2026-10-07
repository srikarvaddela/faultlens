from copy import deepcopy
import hashlib
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app import ollama_client, real_prompting
from app.database import Base, Job, InferenceRun, RealCase, get_session
from app.freeze_real_cases import freeze
from app.jobs import process_one
from app.main import app
from app.ollama_runs import enqueue_run
from app.prompting import digest


def bundle():
    content = 'def calculate():\n    return 9\n'
    return {'id': 'synthetic-real', 'case_label': 'example#1', 'status': 'ready', 'reason': None,
        'sources': [{'path': 'module.py', 'content': content, 'sha256': hashlib.sha256(content.encode()).hexdigest(), 'line_count': 2}],
        'evidence': {'fresh_failing_test_output': 'AssertionError: expected 10, got 9'},
        'oracle': [{'file': 'module.py', 'line': 2, 'kind': 'truth_marker_never_prompted'}], 'provenance': {}}


@pytest.fixture
def factory():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def test_oracle_never_enters_messages_and_inputs_have_stable_hashes():
    first, second = real_prompting.prepare(bundle()), real_prompting.prepare(bundle())
    assert first['plan_sha256'] == second['plan_sha256']
    assert first['id'] != second['id']
    assert 'truth_marker_never_prompted' not in json.dumps(first['first_messages'])
    assert 'scoring_oracle' not in json.dumps(first['first_messages'])
    real_prompting.verify(first)
    changed = deepcopy(first)
    changed['sources'][0]['content'] += 'modified = True\n'
    with pytest.raises(ValueError, match='hash mismatch'):
        real_prompting.verify(changed)


def test_full_file_budget_rejects_large_sources_instead_of_cropping():
    large = bundle()
    content = 'value = 1\n' * 10000
    large['sources'][0].update(content=content, sha256=hashlib.sha256(content.encode()).hexdigest(), line_count=10000)
    with pytest.raises(ValueError, match='context budget'):
        real_prompting.prepare(large)


@pytest.mark.parametrize('candidate', [
    {'file': 'missing.py', 'line': 2, 'reason': 'why'},
    {'file': 'module.py', 'line': True, 'reason': 'why'},
    {'file': 'module.py', 'line': 3, 'reason': 'why'},
    {'file': 'module.py', 'line': 2, 'reason': ''},
])
def test_unknown_files_and_invalid_file_local_lines_fail_strictly(candidate):
    assert not real_prompting.parse_ranking(json.dumps({'candidates': [candidate]}), {'module.py': 2})['valid']


def test_file_identity_is_required_for_scoring_and_duplicate_locations_rejected():
    plan = real_prompting.prepare(bundle())
    parsed = real_prompting.parse_ranking(json.dumps({'candidates': [{'file': 'other.py', 'line': 2, 'reason': 'wrong file'}]}), {'module.py': 2, 'other.py': 2})
    assert parsed['valid']
    assert not real_prompting.score(plan, parsed)['top3']
    correct = {'file': 'module.py', 'line': 2, 'reason': 'why'}
    assert not real_prompting.parse_ranking(json.dumps({'candidates': [correct, correct]}), {'module.py': 2})['valid']
    assert real_prompting.score(plan, {'candidates': [correct]})['top1']


def test_real_queue_saves_requests_before_calls_and_feeds_actual_chain_responses(factory, monkeypatch):
    plans = [real_prompting.prepare(bundle(), strategy) for strategy in ('single', 'chain_evidence')]
    identity = {'name': 'synthetic-local', 'digest': 'hash'}
    monkeypatch.setattr(ollama_client, 'inventory', lambda: {'models': [identity], 'server_version': 'test'})
    with factory() as session:
        session.add(RealCase(id='synthetic-real', created_at='now', payload=bundle()))
        run_id = enqueue_run(session, plans, identity, 'test')['id']
    seen = []
    def chat(request):
        with factory() as session:
            saved = session.get(InferenceRun, run_id).payload
            assert saved['calls'][-1]['request_payload'] == request
            assert saved['calls'][-1]['status'] == 'request_saved'
        seen.append(request)
        content = json.dumps({'candidates': [{'file': 'module.py', 'line': 2, 'reason': 'why'}]}) if 'format' in request else 'Actual real analysis'
        assert 'truth_marker_never_prompted' not in json.dumps(request)
        return {'done': True, 'done_reason': 'stop', 'message': {'content': content}}
    monkeypatch.setattr(ollama_client, 'chat', chat)
    process_one(factory)
    with factory() as session:
        payload = session.get(InferenceRun, run_id).payload
        assert session.get(Job, run_id).status == 'completed'
        assert payload['options']['num_ctx'] == 32768
        assert all(r['top1'] and r['metric'] == 'file_conditioned_patch_location_hit' for r in payload['results'])
    assert len(seen) == 4
    assert 'Actual real analysis' in seen[2]['messages'][1]['content']
    assert seen[0]['format']['properties']['candidates']['items']['properties']['file']['enum'] == ['module.py']


def test_api_rejects_exclusions_and_prepares_registered_real_inputs(factory):
    def override():
        with factory() as session:
            yield session
    app.dependency_overrides[get_session] = override
    with factory() as session:
        ready = bundle()
        excluded = {**bundle(), 'id': 'excluded', 'status': 'excluded', 'reason': 'both revisions fail'}
        session.add_all([RealCase(id=item['id'], created_at='now', payload=item) for item in (ready, excluded)])
        session.commit()
    try:
        client = TestClient(app)
        assert len(client.get('/api/real-cases').json()) == 2
        assert client.post('/api/real-prompt-plans', json={'case_id': 'excluded'}).status_code == 422
        response = client.post('/api/real-prompt-plans', json={'case_id': 'synthetic-real'})
        assert response.status_code == 201
        assert response.json()['kind'] == 'real'
        assert client.get('/api/prompt-plans/' + response.json()['id']).json() == response.json()
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_worker_blocks_withdrawn_input_before_any_model_call(factory, monkeypatch):
    item = bundle()
    plans = [real_prompting.prepare(item)]
    identity = {'name': 'synthetic-local', 'digest': 'hash'}
    with factory() as session:
        session.add(RealCase(id=item['id'], created_at='now', payload={**item, 'status': 'excluded', 'reason': 'Withdrawn missing fixture'}))
        run_id = enqueue_run(session, plans, identity, 'test')['id']
    monkeypatch.setattr(ollama_client, 'inventory', lambda: {'models': [identity], 'server_version': 'test'})
    monkeypatch.setattr(ollama_client, 'chat', lambda _: pytest.fail('withdrawn inputs must never reach the provider'))
    process_one(factory)
    with factory() as session:
        assert session.get(Job, run_id).status == 'failed'
        saved = session.get(InferenceRun, run_id).payload
        assert saved['calls'] == []
        assert 'Withdrawn' in saved['error']


def test_freeze_accepts_only_newline_materialization_and_rejects_changed_source(tmp_path):
    case_dir = tmp_path / 'example-1/buggy'
    case_dir.mkdir(parents=True)
    (case_dir / 'module.py').write_bytes(b'v = 1\r\n')
    for variant in ('buggy', 'fixed'):
        fixture = tmp_path / f'example-1/{variant}/tests/fixture.json'
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_bytes(b'{"value":1}')
    output = 'FAILED regression test'
    case = {'project': 'example', 'bug_id': '1', 'status': 'buggy_fails_fixed_passes', 'ready_for_prompt_review': True,
        'source_import_verified': {'buggy': True, 'fixed': True}, 'sources': [{'path': 'module.py', 'patch_verified': True,
        'sha256': hashlib.sha256(b'v = 1\n').hexdigest(), 'targets': [{'line': 1, 'kind': 'removed_line'}]}],
        'fresh_runs': {'buggy': {'output': output, 'output_sha256': hashlib.sha256(output.encode()).hexdigest()}},
        'test_files': [{'path': 'tests/fixture.json', 'sha256': hashlib.sha256(b'{"value":1}').hexdigest()}]}
    report = {'version': 'faultlens-real-validation-1.1.0', 'benchmark_revision': 'test', 'cases': [case]}
    result = freeze(report, tmp_path)[0]
    assert result['sources'][0]['content'] == 'v = 1\n'
    assert result['provenance']['source_materialization'][0]['crlf_normalized']
    (case_dir / 'module.py').write_bytes(b'v = 99\r\n')
    with pytest.raises(ValueError, match='source bytes changed'):
        freeze(report, tmp_path)
    (case_dir / 'module.py').write_bytes(b'v = 1\r\n')
    (tmp_path / 'example-1/fixed/tests/fixture.json').write_bytes(b'{"value":2}')
    with pytest.raises(ValueError, match='Regression asset bytes'):
        freeze(report, tmp_path)
