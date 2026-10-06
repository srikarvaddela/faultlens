"""Frozen full-file real inputs, with an explicit oracle-file selection caveat."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from .prompting import SYSTEM, digest, render_step

VERSION = 'faultlens-real-prompts-1.0.0'
OPTIONS = {'temperature': 0, 'seed': 42, 'num_predict': 256, 'num_ctx': 32768}
FINAL = 'Return only a JSON object with a "candidates" array. Rank up to three distinct source locations, most suspicious first. Each candidate must have an exact "file" path from the supplied source, an integer "line" in that file, and a short "reason". Do not propose fixes.'


def budget_check(messages, reserve=0):
    # Conservative byte-count preflight, not an exact tokenizer measurement.
    # Leave an additional margin for chat template tokens and output.
    bound = sum(len(message['content'].encode()) for message in messages) + 256 + OPTIONS['num_predict'] + reserve
    if bound > OPTIONS['num_ctx']:
        raise ValueError('Full-file input exceeds conservative context budget; no source cropping or silent truncation allowed')
    return bound


def verify(plan):
    if plan['prompt_version'] != VERSION:
        raise ValueError('Real prompt version changed')
    for source in plan['sources']:
        if hashlib.sha256(source['content'].encode()).hexdigest() != source['sha256']:
            raise ValueError('Frozen real source hash mismatch')
    if digest(plan['evidence']) != plan['evidence_sha256'] or digest(plan['sources']) != plan['source_sha256']:
        raise ValueError('Frozen real input hash mismatch')
    if plan['source'] != numbered_source(plan['sources']):
        raise ValueError('Numbered real source differs from frozen files')
    if plan['first_messages'] != render_step(plan, 0, []):
        raise ValueError('Materialized first prompt differs from frozen input')
    if digest(plan['scoring_oracle']) != plan['oracle_sha256']:
        raise ValueError('Frozen scoring oracle hash mismatch')


def numbered_source(sources):
    return '\n\n'.join('File: ' + source['path'] + '\n' + '\n'.join(f'{index}: {line}' for index, line in enumerate(source['content'].splitlines(), 1)) for source in sources)


def prepare(bundle, strategy='single'):
    if bundle['status'] != 'ready' or strategy not in ('single', 'chain_evidence'):
        raise ValueError(bundle.get('reason') or 'Real case is not ready')
    plan = {'id': str(uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(),
        'kind': 'real', 'bug_id': bundle['case_label'], 'real_case_id': bundle['id'],
        'prompt_version': VERSION, 'status': 'prepared_no_inference', 'strategy': strategy,
        'evidence_mode': 'fresh_regression_output', 'carry_evidence': True,
        'sources': deepcopy(bundle['sources']), 'source': numbered_source(bundle['sources']),
        'source_sha256': digest(bundle['sources']), 'evidence': deepcopy(bundle['evidence']),
        'evidence_sha256': digest(bundle['evidence']), 'scoring_oracle': deepcopy(bundle['oracle']),
        'oracle_sha256': digest(bundle['oracle']), 'system_instruction': SYSTEM,
        'final_output_instruction': FINAL,
        'steps': ['Localize fault'] if strategy == 'single' else ['Understand failure', 'Identify suspicious locations', 'Localize fault'],
        'provenance': deepcopy(bundle['provenance']), 'notes': [
            'File-conditioned localization: changed files were selected using the benchmark patch. This is oracle-assisted file selection, not repository-wide fault localization.',
            'Complete buggy files and fresh failing-test output are frozen. No windows are chosen around ground-truth lines. Patch text, changed lines, fixed source, and oracle labels are excluded from model messages.',
            'Failure output may reveal target names or lines. Evidence is not certified leakage-free; no historical study reproduction is claimed.',
            'Patch-location hit scores any removed old-file line or marked additive anchor; it does not grade explanation correctness.',
        ]}
    plan['first_messages'] = render_step(plan, 0, [])
    plan['first_messages_sha256'] = digest(plan['first_messages'])
    plan['plan_sha256'] = digest({k: v for k, v in plan.items() if k not in ('id', 'created_at')})
    # Gate against the full source/evidence pair for both methods, reserving space
    # for two bounded intermediate responses. Recheck actual messages per call.
    single = deepcopy(plan)
    single['strategy'] = 'single'; single['steps'] = ['Localize fault']
    budget_check(render_step(single, 0, []), reserve=8192)
    return plan


def parse_ranking(text, file_lines):
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return {'valid': False, 'error': 'invalid_json', 'candidates': []}
    if not isinstance(data, dict) or set(data) != {'candidates'} or not isinstance(data['candidates'], list) or not 1 <= len(data['candidates']) <= 3:
        return {'valid': False, 'error': 'invalid_schema', 'candidates': []}
    seen = set()
    for candidate in data['candidates']:
        if not isinstance(candidate, dict) or set(candidate) != {'file', 'line', 'reason'}:
            return {'valid': False, 'error': 'invalid_candidate', 'candidates': []}
        file, line = candidate['file'], candidate['line']
        if not isinstance(file, str) or file not in file_lines or type(line) is not int or not 1 <= line <= file_lines[file] or (file, line) in seen or not isinstance(candidate['reason'], str) or not candidate['reason'].strip() or len(candidate['reason']) > 2000:
            return {'valid': False, 'error': 'invalid_candidate', 'candidates': []}
        seen.add((file, line))
    return {'valid': True, 'error': None, 'candidates': data['candidates']}


def score(plan, parsed):
    oracle = {(item['file'], item['line']) for item in plan['scoring_oracle']}
    rank = next((i + 1 for i, candidate in enumerate(parsed['candidates']) if (candidate['file'], candidate['line']) in oracle), None)
    return {'fault_rank': rank, 'top1': rank == 1, 'top3': rank is not None, 'reciprocal_rank': 1 / rank if rank else 0,
            'grading_oracle': plan['scoring_oracle'], 'metric': 'file_conditioned_patch_location_hit'}
