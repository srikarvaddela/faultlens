"""Local inference with persisted calls, bounded generation, and no silent replay."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import logging
import threading
import time
from uuid import uuid4

from sqlalchemy import update

from .catalog import BY_ID
from .database import InferenceRun, Job
from .jobs import owned, heartbeat, LEASE_SECONDS, job_view
from . import ollama_client
from .prompting import digest, render_step, parse_ranking, VERSION

OPTIONS = {'temperature': 0, 'seed': 42, 'num_predict': 256, 'num_ctx': 4096}


def enqueue_run(session, plans, identity, server_version):
    job_id = str(uuid4())
    created = datetime.now(timezone.utc).isoformat()
    payload = {'id': job_id, 'created_at': created, 'provider': 'ollama_local', 'plans': deepcopy(plans), 'model_identity': identity, 'server_version': server_version, 'options': dict(OPTIONS), 'calls': [], 'results': [], 'error': None, 'notes': ['Curated-case smoke test, not a benchmark or reproduction of the GPT-5 study.', 'No automatic inference replay after errors or worker restarts. Cancellation is cooperative between bounded calls.']}
    session.add(InferenceRun(id=job_id, created_at=created, payload=payload))
    session.add(Job(id=job_id, name=f'Ollama · {plans[0]["bug_id"]} · {identity["name"]}', created_at=created, request={'kind': 'ollama', 'bug_ids': [plan['bug_id'] for plan in plans], 'methods': ['ollama']}))
    session.commit()
    return job_view(session.get(Job, job_id))


def checkpoint(factory, job_id, token, mutate):
    with factory() as session:
        changed = session.execute(update(Job).where(owned(job_id, token)).values(lease_until=time.time() + LEASE_SECONDS))
        if not changed.rowcount:
            session.rollback()
            return False
        run = session.get(InferenceRun, job_id)
        payload = deepcopy(run.payload)
        mutate(payload)
        run.payload = payload
        session.commit()
        return True


def terminal(factory, job_id, token, status, error=None):
    with factory() as session:
        changed = session.execute(update(Job).where(owned(job_id, token)).values(status=status, lease_token=None, last_error=error))
        if not changed.rowcount:
            session.rollback()
            return
        run = session.get(InferenceRun, job_id)
        if run:
            payload = deepcopy(run.payload)
            payload['error'] = error
            run.payload = payload
        session.commit()


def keep_lease(factory, job_id, token, stop):
    while not stop.wait(5):
        with factory() as session:
            session.execute(update(Job).where(owned(job_id, token)).values(lease_until=time.time() + LEASE_SECONDS))
            session.commit()


def run_owned(factory, job_id, token):
    with factory() as session:
        job = session.get(Job, job_id)
        run = session.get(InferenceRun, job_id)
        payload = deepcopy(run.payload) if run else None
        attempts = job.attempts
    if not payload:
        terminal(factory, job_id, token, 'failed', 'Inference snapshot missing')
        return
    if attempts != 1:
        terminal(factory, job_id, token, 'failed', 'Worker restarted; prior call completion may be uncertain. Retry explicitly to start a new run.')
        return
    try:
        identity = payload['model_identity']
        inventory = ollama_client.inventory()
        if not any(model['name'] == identity['name'] and model['digest'] == identity['digest'] for model in inventory['models']):
            raise ollama_client.OllamaError('Installed model identity changed; prepare a new run')
        for plan_index, plan in enumerate(payload['plans']):
            if plan['prompt_version'] != VERSION or hashlib.sha256(BY_ID[plan['bug_id']]['source'].encode()).hexdigest() != plan['source_sha256']:
                raise ollama_client.OllamaError('Plan source or prompt version changed')
            responses = []
            for step in range(len(plan['steps'])):
                if not heartbeat(factory, job_id, token, plan_index):
                    return
                current = ollama_client.inventory()
                if not any(model['name'] == identity['name'] and model['digest'] == identity['digest'] for model in current['models']):
                    raise ollama_client.OllamaError('Model identity changed between calls')
                if payload.get('server_version') and current.get('server_version') != payload['server_version']:
                    raise ollama_client.OllamaError('Ollama server version changed between calls')
                messages = deepcopy(plan['first_messages']) if step == 0 else render_step(plan, step, responses)
                request_payload = ollama_client.build_request(identity['name'], messages, payload['options'], step == len(plan['steps']) - 1, len(plan['source'].splitlines()))
                call = {'plan_id': plan['id'], 'strategy': plan['strategy'], 'step': step + 1, 'server_version': current.get('server_version'), 'messages': messages, 'messages_sha256': digest(messages), 'request_payload': request_payload, 'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'request_saved', 'response': None}
                if not checkpoint(factory, job_id, token, lambda saved: saved['calls'].append(call)):
                    return
                stop = threading.Event()
                lease_thread = threading.Thread(target=keep_lease, args=(factory, job_id, token, stop), daemon=True)
                lease_thread.start()
                started = time.perf_counter()
                try:
                    response = ollama_client.chat(request_payload)
                finally:
                    stop.set(); lease_thread.join(timeout=6)
                message = response.get('message', {})
                content = message.get('content') if isinstance(message, dict) else None
                if response.get('done') is not True or not isinstance(content, str) or not content.strip():
                    raise ollama_client.OllamaError('Ollama returned an incomplete or empty response')
                completed = {'status': 'completed', 'request_payload': request_payload, 'response': response, 'response_sha256': digest(response), 'latency_ms': round((time.perf_counter() - started) * 1000, 2)}
                if not checkpoint(factory, job_id, token, lambda saved: saved['calls'][-1].update(completed)):
                    return
                responses.append(content)
            if not heartbeat(factory, job_id, token, plan_index + 1):
                return
            parsed = parse_ranking(responses[-1], len(plan['source'].splitlines()))
            rank = next((index + 1 for index, candidate in enumerate(parsed['candidates']) if candidate['line'] == BY_ID[plan['bug_id']]['fault_line']), None)
            result = {'plan_id': plan['id'], 'strategy': plan['strategy'], 'parse': parsed, 'fault_rank': rank, 'top1': rank == 1, 'top3': rank is not None and rank <= 3, 'reciprocal_rank': 1 / rank if rank else 0, 'grading_fault_line': BY_ID[plan['bug_id']]['fault_line']}
            if not checkpoint(factory, job_id, token, lambda saved: saved['results'].append(result)):
                return
        terminal(factory, job_id, token, 'completed')
    except ollama_client.OllamaError as exc:
        terminal(factory, job_id, token, 'failed', str(exc))
    except Exception:
        logging.exception('Local inference %s failed', job_id)
        terminal(factory, job_id, token, 'failed', 'Local inference failed; inspect saved calls and worker logs')
