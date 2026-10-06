import importlib.util
from pathlib import Path
import sys


def test_real_export_retains_failures_but_excludes_private_text():
    scripts = Path(__file__).resolve().parents[2] / 'scripts'
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location('real_benchmark', scripts / 'benchmark_real.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts))
    batch = {'created_at': 'now', 'selection': [{'id': 'case', 'case_label': 'example#1', 'status': 'ready', 'reason': None, 'files': []}],
        'entries': [{'case_label': 'example#1', 'run': {'id': 'run', 'status': 'failed', 'model_identity': {'name': 'test', 'digest': 'hash'}, 'server_version': 'test', 'options': {},
            'plans': [], 'results': [], 'calls': [{'strategy': 'single', 'step': 1, 'status': 'completed', 'messages_sha256': 'messagehash',
            'request_payload': {'messages': [{'content': 'PRIVATE research text and paths'}]},
            'response': {'message': {'content': 'PRIVATE output'}, 'prompt_eval_count': 30, 'eval_count': 10, 'done_reason': 'length'}}]}}]}
    output = module.public_results(batch)
    assert 'PRIVATE' not in str(output)
    assert output['entries'][0]['status'] == 'failed'
    assert output['entries'][0]['calls'][0]['done_reason'] == 'length'
    assert output['entries'][0]['calls'][0]['input_tokens'] == 30
