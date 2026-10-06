"""Run a checkpointed curated benchmark against the local FaultLens API.

Uses only the standard library. Failed runs are retained, never retried silently.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import time
from urllib.request import Request, build_opener, ProxyHandler


def save(path, payload):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def summarize(entries):
    rows = []
    for entry in entries:
        run = entry['run']
        for strategy in ('single', 'chain_evidence'):
            result = next((r for r in run['results'] if r['strategy'] == strategy), None)
            calls = [c for c in run['calls'] if c['strategy'] == strategy]
            responses = [c['response'] for c in calls if c.get('response')]
            rows.append({
                'bug_id': entry['bug_id'], 'repeat': entry['repeat'], 'strategy': strategy,
                'status': run['status'], 'parse_valid': bool(result and result['parse']['valid']),
                'fault_rank': result['fault_rank'] if result else None,
                'top1': bool(result and result['top1']), 'top3': bool(result and result['top3']),
                'reciprocal_rank': result['reciprocal_rank'] if result else 0,
                'calls_completed': len(responses),
                'truncated_calls': sum(r.get('done_reason') == 'length' for r in responses),
                'input_tokens': sum(r.get('prompt_eval_count', 0) for r in responses),
                'output_tokens': sum(r.get('eval_count', 0) for r in responses),
                'latency_ms': sum(c.get('latency_ms', 0) for c in calls),
                'load_ms': sum(r.get('load_duration', 0) / 1e6 for r in responses),
            })
    return rows


def validate_batch(entries):
    """Reject pooled reporting if model, options, or frozen inputs drift."""
    identities, sources = set(), {}
    for entry in entries:
        run = entry.get('run')
        if not run:
            continue
        identities.add(json.dumps([run['model_identity']['name'], run['model_identity']['digest'],
                                   run['server_version'], run['options']], sort_keys=True))
        for plan in run['plans']:
            signature = (plan['source_sha256'], plan['evidence_sha256'], plan['prompt_version'], plan['evidence_mode'])
            previous = sources.setdefault(entry['bug_id'], signature)
            if previous != signature:
                raise ValueError('Frozen source, evidence, or prompt configuration changed within the batch')
    if len(identities) > 1:
        raise ValueError('Model identity, runtime, or generation options changed within the batch')


def report(batch):
    rows = batch['rows']
    first = batch['entries'][0]['run']
    lines = ['# Local Ollama curated benchmark', '',
             f"Model: `{batch['model']}`. Digest: `{first['model_identity']['digest']}`. Ollama: `{first['server_version']}`.", '',
             f"Six original educational Python bugs, {batch['repeats']} repeats per bug, single prompt versus a three-step chain carrying failure evidence. Inputs use `{batch['evidence_mode']}`. Exact requests, responses, identities, hashes, and timings are in [the JSON export](" + Path(batch['filename']).name + ').', '',
             f"Generation options: `{json.dumps(first['options'], sort_keys=True)}`. Both strategies receive the same frozen source and evidence for each paired run. Ground truth is used only after inference for scoring.", '',
             f"Inference implementation revision: `{batch.get('implementation_revision', 'unrecorded')}`. Runner platform: `{batch.get('runner_platform', 'unrecorded')}`. This records the API implementation revision; benchmark tooling is committed afterward. It does not capture a complete hardware/environment manifest.", '',
             '## Results', '',
             '| Strategy | Trials | Top-1 | Top-3 | MRR | Valid finals | Truncated calls | Input / output tokens | Wall / load seconds |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for strategy in ('single', 'chain_evidence'):
        selected = [r for r in rows if r['strategy'] == strategy]
        n = len(selected)
        lines.append(f"| {strategy} | {n} | {sum(r['top1'] for r in selected)/n:.1%} | {sum(r['top3'] for r in selected)/n:.1%} | {sum(r['reciprocal_rank'] for r in selected)/n:.4f} | {sum(r['parse_valid'] for r in selected)}/{n} | {sum(r['truncated_calls'] for r in selected)} | {sum(r['input_tokens'] for r in selected)} / {sum(r['output_tokens'] for r in selected)} | {sum(r['latency_ms'] for r in selected)/1000:.2f} / {sum(r['load_ms'] for r in selected)/1000:.2f} |")
    lines += ['', '| Bug | Single fault ranks by repeat | Chain fault ranks by repeat |', '|---|---|---|']
    for bug in batch['bug_ids']:
        ranks = []
        for strategy in ('single', 'chain_evidence'):
            selected = sorted((r for r in rows if r['bug_id'] == bug and r['strategy'] == strategy), key=lambda r: r['repeat'])
            ranks.append(', '.join(str(r['fault_rank']) if r['fault_rank'] else 'miss' if r['parse_valid'] else 'invalid/unavailable' for r in selected))
        lines.append(f'| {bug} | {ranks[0]} | {ranks[1]} |')
    calls = [c for e in batch['entries'] for c in e['run']['calls']]
    lines += ['', f"Completed model calls: {sum(c['status'] == 'completed' for c in calls)}/{len(calls)} saved calls. Terminal run statuses: `{json.dumps({s: sum(e['run']['status'] == s for e in batch['entries']) for s in ('completed', 'failed', 'cancelled')})}`.", '',
              '## Interpretation and limits', '',
              '- All planned strategy trials are included in accuracy denominators; invalid or unavailable finals score zero. Parse validity is reported separately. No failed calls are silently retried.',
              '- Repeats share seed 42 and temperature zero. They measure observed repeatability, not 18 independent bugs. No significance test or general accuracy claim is supported by six fixtures.',
              '- Candidate rank checks the known faulty line only. Valid JSON and a correct line do not establish correct reasoning. Explanations were not semantically graded.',
              '- Truncation counts any response with `done_reason=length`, including intermediate chain steps. Later steps receive the actual truncated text.',
              '- Single runs precede chain runs within every pair. Native load time is included in wall latency; cache, loading, ordering, and local hardware confound speed comparisons. Summed latency covers model HTTP calls only, not evidence collection or queue time.',
              '- These prompts and fixtures do not reproduce the archived university study or establish leakage-free real-world performance. This is an engineering baseline for the local inference pipeline.', '',
              '## Reproduce', '', 'Start the native API, worker, and Ollama with the installed model, then run from the repository root:', '', '```shell',
              'python scripts/benchmark_ollama.py --model llama3.2:1b --repeats 3 --output benchmark-local.json', '```', '',
              'Use a new output path for a new batch. An existing file resumes known run IDs without replaying them. If submission completion is uncertain, the runner stops for reconciliation. Model output and timing may differ on another runtime or hardware.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='llama3.2:1b')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10:
        parser.error('repeats must be between 1 and 10')
    opener = build_opener(ProxyHandler({}))

    def api(route, body=None):
        request = Request('http://127.0.0.1:8000/api/' + route,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=30) as response:
            return json.load(response)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        batch = json.loads(args.output.read_text(encoding='utf-8'))
        if batch['model'] != args.model or batch['repeats'] != args.repeats:
            parser.error('existing batch configuration differs')
    else:
        revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True).stdout.strip()
        batch = {'version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                 'model': args.model, 'repeats': args.repeats, 'evidence_mode': 'failure_details',
                 'implementation_revision': revision, 'runner_platform': platform.platform(),
                 'bug_ids': [b['id'] for b in api('catalog')['bugs']], 'entries': []}
        save(args.output, batch)
    for repeat in range(1, args.repeats + 1):
        for bug_id in batch['bug_ids']:
            entry = next((e for e in batch['entries'] if e['bug_id'] == bug_id and e['repeat'] == repeat), None)
            if entry is None:
                plan = api('prompt-plans', {'bug_id': bug_id, 'strategy': 'single', 'evidence_mode': batch['evidence_mode']})
                entry = {'bug_id': bug_id, 'repeat': repeat, 'plan_id': plan['id'], 'run_id': None}
                batch['entries'].append(entry)
                # Mark submission before the POST. A crash here requires reconciliation,
                # since the server may have accepted it without returning the response.
                save(args.output, batch)
                job = api('ollama/runs', {'plan_id': plan['id'], 'model': args.model, 'compare': True})
                entry['run_id'] = job['id']
                save(args.output, batch)
            if entry['run_id'] is None:
                raise RuntimeError('Uncertain submission: reconcile the saved plan with local runs before resuming; do not silently replay')
            while True:
                run = api('ollama/runs/' + entry['run_id'])
                if run['status'] in ('completed', 'failed', 'cancelled'):
                    entry['run'] = run
                    save(args.output, batch)
                    validate_batch(batch['entries'])
                    print(f"{bug_id} repeat {repeat}: {run['status']} ({len(run['calls'])} calls)", flush=True)
                    break
                time.sleep(2)
    batch['rows'] = summarize(batch['entries'])
    batch['completed_at'] = datetime.now(timezone.utc).isoformat()
    batch['filename'] = args.output.name
    save(args.output, batch)
    args.output.with_suffix('.md').write_text(report(batch), encoding='utf-8')


if __name__ == '__main__':
    main()
