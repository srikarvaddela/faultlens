"""One predefined comparison per ready real case; private transcripts stay local."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, build_opener, ProxyHandler

from benchmark_ollama import save


def public_results(batch):
    """Export measurements and hashes only; keep input/output text local."""
    entries = []
    for entry in batch['entries']:
        run = entry['run']
        calls = []
        for call in run['calls']:
            response = call.get('response') or {}
            calls.append({'strategy': call['strategy'], 'step': call['step'], 'status': call['status'],
                'messages_sha256': call['messages_sha256'], 'response_sha256': call.get('response_sha256'),
                'request_sha256': hashlib.sha256(json.dumps(call['request_payload'], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                'latency_ms': call.get('latency_ms'), 'input_tokens': response.get('prompt_eval_count'),
                'output_tokens': response.get('eval_count'), 'done_reason': response.get('done_reason'),
                'load_ms': response.get('load_duration', 0) / 1e6})
        entries.append({'case_label': entry['case_label'], 'evidence_mode': entry.get('evidence_mode', 'fresh_regression_output'), 'run_id': run['id'], 'status': run['status'],
            'model_identity': run['model_identity'], 'server_version': run['server_version'], 'options': run['options'],
            'inputs': [{'strategy': p['strategy'], 'plan_sha256': p['plan_sha256'], 'source_sha256': p['source_sha256'],
                        'evidence_sha256': p['evidence_sha256'], 'evidence_parent_sha256': p.get('evidence_parent_sha256'),
                        'evidence_transform_version': p.get('evidence_transform_version'), 'oracle_sha256': p['oracle_sha256'], 'prompt_version': p['prompt_version']} for p in run['plans']],
            'results': [{key: r[key] for key in ('strategy', 'fault_rank', 'top1', 'top3', 'reciprocal_rank', 'metric')} |
                        {'parse_valid': r['parse']['valid'], 'parse_error': r['parse']['error']} for r in run['results']], 'calls': calls})
    return {'created_at': batch['created_at'], 'completed_at': batch.get('completed_at'),
        'evidence_modes': batch.get('evidence_modes', ['fresh_regression_output']),
        'condition_order': batch.get('condition_order', 'One evidence condition'),
        'selection': [{key: case[key] for key in ('id', 'case_label', 'status', 'reason', 'files')} for case in batch['selection']],
        'entries': entries, 'scope': 'Full-file, file-conditioned patch-location hits; oracle-assisted file selection. No repository-wide or leakage-free claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', default='llama3.2:1b')
    parser.add_argument('--public-summary', type=Path, help='Export metrics/hashes without private transcripts')
    parser.add_argument('--case-ids', help='Explicit comma-separated registry IDs when multiple snapshots exist per case')
    parser.add_argument('--ablation', action='store_true', help='Compare full failure output against exception-type-only evidence, with alternating condition order')
    args = parser.parse_args()
    opener = build_opener(ProxyHandler({}))
    def api(route, body=None):
        request = Request('http://127.0.0.1:8000/api/' + route,
            data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=30) as response:
            return json.load(response)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        batch = json.loads(args.output.read_text(encoding='utf-8'))
        if batch['model'] != args.model:
            parser.error('existing batch model differs')
        if bool(batch.get('ablation')) != args.ablation:
            parser.error('existing batch evidence conditions differ')
    else:
        selection = api('real-cases')
        if args.case_ids:
            chosen = args.case_ids.split(',')
            if len(chosen) != len(set(chosen)) or not set(chosen).issubset({c['id'] for c in selection}):
                parser.error('case IDs must be unique registered snapshots')
            selection = [c for c in selection if c['id'] in chosen]
        if len({c['case_label'] for c in selection}) != len(selection):
            raise ValueError('Multiple snapshots of a bug exist. Select one per case with --case-ids; do not pool duplicate bugs.')
        batch = {'created_at': datetime.now(timezone.utc).isoformat(), 'model': args.model,
                 'selection': selection, 'entries': [], 'ablation': args.ablation,
                 'evidence_modes': ['fresh_regression_output', 'exception_type_only'] if args.ablation else ['fresh_regression_output'],
                 'condition_order': 'Alternating full-first/type-only-first by selection index; single before chain within every condition' if args.ablation else 'One evidence condition'}
        save(args.output, batch)
    if not batch['selection']:
        raise ValueError('No frozen real cases registered')
    ready_index = 0
    for case in batch['selection']:
        if case['status'] != 'ready':
            print(case['case_label'] + ': excluded · ' + case['reason'], flush=True)
            continue
        modes = batch.get('evidence_modes', ['fresh_regression_output'])
        if ready_index % 2:
            modes = list(reversed(modes))
        ready_index += 1
        for mode in modes:
            entry = next((e for e in batch['entries'] if e['case_id'] == case['id'] and e.get('evidence_mode', 'fresh_regression_output') == mode), None)
            if entry is None:
                plan = api('real-prompt-plans', {'case_id': case['id'], 'evidence_mode': mode})
                entry = {'case_id': case['id'], 'case_label': case['case_label'], 'evidence_mode': mode, 'plan_id': plan['id'], 'run_id': None}
                batch['entries'].append(entry)
                save(args.output, batch)
                job = api('ollama/runs', {'plan_id': plan['id'], 'model': args.model, 'compare': True})
                entry['run_id'] = job['id']
                save(args.output, batch)
            if not entry['run_id']:
                raise ValueError('Uncertain submission; reconcile saved plan before resuming. No silent replay.')
            while True:
                run = api('ollama/runs/' + entry['run_id'])
                if run['status'] in ('completed', 'failed', 'cancelled'):
                    entry['run'] = run
                    save(args.output, batch)
                    print(f"{case['case_label']} {mode}: {run['status']} ({len(run['calls'])} calls)", flush=True)
                    break
                time.sleep(2)
    identities = {(e['run']['model_identity']['digest'], e['run']['server_version'], json.dumps(e['run']['options'], sort_keys=True)) for e in batch['entries']}
    if len(identities) != 1:
        raise ValueError('Mixed runtime identities; do not pool results')
    validate_pairing(batch)
    batch.setdefault('completed_at', datetime.now(timezone.utc).isoformat())
    save(args.output, batch)
    if args.public_summary:
        args.public_summary.parent.mkdir(parents=True, exist_ok=True)
        save(args.public_summary, public_results(batch))


def validate_pairing(batch):
    for case in (c for c in batch['selection'] if c['status'] == 'ready'):
        entries = [e for e in batch['entries'] if e['case_id'] == case['id']]
        modes = batch.get('evidence_modes', ['fresh_regression_output'])
        if sorted(e.get('evidence_mode', 'fresh_regression_output') for e in entries) != sorted(modes):
            raise ValueError('Missing or duplicate evidence conditions')
        shared = set()
        for entry in entries:
            if entry['run'].get('validation_warning'):
                raise ValueError('A frozen snapshot has been superseded; retain the historical run and benchmark corrected inputs')
            plans = entry['run']['plans']
            if len(plans) != 2 or {p['strategy'] for p in plans} != {'single', 'chain_evidence'}:
                raise ValueError('Missing paired strategies')
            if any(p['evidence_mode'] != entry.get('evidence_mode', 'fresh_regression_output') for p in plans):
                raise ValueError('Server returned the wrong evidence condition')
            if len({p['evidence_sha256'] for p in plans}) != 1:
                raise ValueError('Strategies did not share frozen evidence')
            shared.update((p['source_sha256'], p['oracle_sha256'], p.get('evidence_parent_sha256', p['evidence_sha256'])) for p in plans)
        if len(shared) != 1:
            raise ValueError('Source, oracle, or parent evidence changed across conditions')
        if len(modes) > 1 and len({e['run']['plans'][0]['evidence_sha256'] for e in entries}) != len(modes):
            raise ValueError('Ablation conditions did not change frozen evidence')


if __name__ == '__main__':
    main()
