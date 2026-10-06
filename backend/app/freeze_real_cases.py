"""Offline: freeze fresh validated source/evidence into the local registry."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .database import RealCase, SessionLocal, initialize_database
from .prompting import digest
from .real_prompting import prepare
from .validate_real_cases import safe_path


def freeze(report, directory):
    bundles = []
    for case in report['cases']:
        bundle = {'case_label': f"{case['project']}#{case['bug_id']}", 'sources': [], 'evidence': {}, 'oracle': [],
            'status': 'excluded', 'reason': case['status'], 'provenance': {
                'validation_sha256': digest(report), 'benchmark_revision': report['benchmark_revision'],
                'project': case['project'], 'bug_id': case['bug_id'], 'upstream': case.get('upstream'),
                'buggy_commit': case.get('buggy_commit'), 'fixed_commit': case.get('fixed_commit'),
                'reproduction_status': case['status'], 'deviations': case.get('deviations', [])}}
        if case.get('ready_for_prompt_review') and case['status'] == 'buggy_fails_fixed_passes':
            if not all(case.get('source_import_verified', {}).get(v) is True for v in ('buggy', 'fixed')):
                raise ValueError('Source import verification missing')
            for source in case['sources']:
                if not source['patch_verified']:
                    raise ValueError('Patch verification missing')
                path = safe_path(directory / f"{case['project']}-{case['bug_id']}" / 'buggy', source['path'])
                data = path.read_bytes()
                canonical = data.replace(b'\r\n', b'\n')
                materialized_sha = hashlib.sha256(data).hexdigest()
                if materialized_sha != source['sha256'] and hashlib.sha256(canonical).hexdigest() != source['sha256']:
                    raise ValueError('Validated source bytes changed before freezing')
                content = (canonical if materialized_sha != source['sha256'] else data).decode('utf-8')
                bundle['provenance'].setdefault('source_materialization', []).append({'file': source['path'],
                    'workspace_sha256': materialized_sha, 'pinned_blob_sha256': source['sha256'],
                    'crlf_normalized': materialized_sha != source['sha256']})
                bundle['sources'].append({'path': source['path'], 'content': content, 'sha256': hashlib.sha256(content.encode()).hexdigest(), 'line_count': len(content.splitlines())})
                bundle['oracle'] += [{'file': source['path'], 'line': t['line'], 'kind': t['kind']} for t in source['targets']]
            output = case['fresh_runs']['buggy']['output']
            if hashlib.sha256(output.encode()).hexdigest() != case['fresh_runs']['buggy']['output_sha256']:
                raise ValueError('Validated failure output changed before freezing')
            bundle['evidence'] = {'fresh_failing_test_output': output}
            bundle['status'], bundle['reason'] = 'ready', None
            if not bundle['oracle']:
                bundle['status'], bundle['reason'] = 'excluded', 'No patch-location oracle'
        bundle['id'] = digest(bundle)
        if bundle['status'] == 'ready':
            try:
                prepare(bundle)
            except ValueError as exc:
                bundle['status'], bundle['reason'] = 'excluded', str(exc)
                bundle['id'] = digest({k: v for k, v in bundle.items() if k != 'id'})
        bundles.append(bundle)
    return bundles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('validation', type=Path)
    args = parser.parse_args()
    report = json.loads(args.validation.read_text(encoding='utf-8'))
    bundles = freeze(report, args.validation.parent)
    initialize_database()
    with SessionLocal() as session:
        for bundle in bundles:
            if not session.get(RealCase, bundle['id']):
                session.add(RealCase(id=bundle['id'], created_at=datetime.now(timezone.utc).isoformat(), payload=bundle))
            print(json.dumps({'id': bundle['id'], 'case': bundle['case_label'], 'status': bundle['status'], 'reason': bundle['reason']}))
        session.commit()


if __name__ == '__main__':
    main()
