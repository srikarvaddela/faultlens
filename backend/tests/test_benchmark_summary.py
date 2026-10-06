"""Ensure benchmark failures stay in denominators and native usage is retained."""
import importlib.util
from pathlib import Path
from copy import deepcopy
import pytest

spec = importlib.util.spec_from_file_location('benchmark', Path(__file__).resolve().parents[2] / 'scripts' / 'benchmark_ollama.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_summary_retains_failed_and_invalid_trials():
    rows = benchmark.summarize([{'bug_id': 'FL-001', 'repeat': 1, 'run': {
        'status': 'failed', 'results': [{'strategy': 'single', 'parse': {'valid': False},
        'fault_rank': None, 'top1': False, 'top3': False, 'reciprocal_rank': 0}],
        'calls': [{'strategy': 'single', 'latency_ms': 120, 'response': {
            'prompt_eval_count': 20, 'eval_count': 10, 'load_duration': 50000000,
            'done_reason': 'length'}}, {'strategy': 'chain_evidence', 'response': None}]
    }}])
    assert len(rows) == 2
    assert all(not r['parse_valid'] and r['reciprocal_rank'] == 0 for r in rows)
    assert rows[0]['truncated_calls'] == 1
    assert rows[0]['input_tokens'] == 20
    assert rows[0]['output_tokens'] == 10
    assert rows[0]['load_ms'] == 50
    assert rows[1]['calls_completed'] == 0


def test_batch_rejects_model_and_evidence_drift():
    entry = {'bug_id': 'FL-001', 'run': {'model_identity': {'name': 'local', 'digest': 'a'},
        'server_version': '1', 'options': {'seed': 42}, 'plans': [{'source_sha256': 's',
        'evidence_sha256': 'e', 'prompt_version': 'p', 'evidence_mode': 'failure_details'}]}}
    other = deepcopy(entry)
    benchmark.validate_batch([entry, other])
    other['run']['model_identity']['digest'] = 'b'
    with pytest.raises(ValueError, match='Model identity'):
        benchmark.validate_batch([entry, other])
    other = deepcopy(entry)
    other['run']['plans'][0]['evidence_sha256'] = 'changed'
    with pytest.raises(ValueError, match='Frozen source'):
        benchmark.validate_batch([entry, other])
