"""Static provenance checks and conservative fresh-reproduction classification."""
import ast
import hashlib
import re

VERSION = 'faultlens-real-validation-1.0.0'
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
SETUP_FAILURE = re.compile(r'ImportError|ModuleNotFoundError|command not found|ERROR collecting|collected 0 items|Ran 0 tests|No module named|not found:|unrecognized arguments', re.I)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def info(text):
    return dict(re.findall(r'^(\w+)="([^"\n]*)"', text, re.M))


def patch_sections(patch):
    sections, current, hunk = [], None, None
    for line in patch.splitlines():
        if line.startswith('diff --git '):
            current, hunk = None, None
        elif line.startswith('--- a/'):
            current = {'path': line[6:], 'hunks': []}
            sections.append(current)
        elif current and HUNK.match(line):
            match = HUNK.match(line)
            hunk = {'start': int(match[1]), 'old_count': int(match[2] or 1), 'lines': []}
            current['hunks'].append(hunk)
        elif hunk is not None and line[:1] in (' ', '-', '+') and not line.startswith('+++'):
            hunk['lines'].append(line)
    if not sections or any(not s['hunks'] for s in sections):
        raise ValueError('Unsupported or empty patch')
    return sections


def check_source(section, data, fixed_data=None):
    source = data.decode('utf-8-sig')
    lines = source.splitlines()
    targets, problems = [], []
    patched, cursor = [], 0
    for hunk in section['hunks']:
        old = [line[1:] for line in hunk['lines'] if line[0] in (' ', '-')]
        start = hunk['start'] - 1 if hunk['old_count'] else hunk['start']
        if len(old) != hunk['old_count'] or lines[start:start + len(old)] != old:
            problems.append('patch_old_context_mismatch')
            continue
        patched += lines[cursor:start] + [line[1:] for line in hunk['lines'] if line[0] in (' ', '+')]
        cursor = start + len(old)
        number, removed, anchors = start, [], []
        for line in hunk['lines']:
            if line[0] in (' ', '-'):
                number += 1
            if line[0] == '-':
                removed.append(number)
            elif line[0] == '+':
                anchors.append(max(1, min(number, len(lines))))
        targets += [{'line': n, 'kind': 'removed_line'} for n in removed] if removed else [{'line': n, 'kind': 'insertion_anchor'} for n in sorted(set(anchors))]
    try:
        tree = ast.parse(source)
        spans = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for target in targets:
            containing = [n for n in spans if n.lineno <= target['line'] <= n.end_lineno]
            target['function'] = min(containing, key=lambda n: n.end_lineno - n.lineno).name if containing else None
    except SyntaxError:
        problems.append('source_ast_unavailable')
    unique = list({(t['line'], t['kind']): t for t in targets}.values())
    patched += lines[cursor:]
    if fixed_data is not None and patched != fixed_data.decode('utf-8-sig').splitlines():
        problems.append('fixed_source_differs_from_benchmark_patch')
    return {'path': section['path'], 'sha256': sha256(data), 'line_count': len(lines),
            'fixed_sha256': sha256(fixed_data) if fixed_data is not None else None,
            'patch_verified': not problems, 'problems': sorted(set(problems)), 'targets': unique}


def reproduction_status(buggy, fixed):
    if buggy.get('timeout') or fixed.get('timeout'):
        return 'timeout'
    if any(SETUP_FAILURE.search(run.get('output', '')) for run in (buggy, fixed)):
        return 'environment_failure'
    # pytest exit 1 and unittest exit 1 require explicit assertion/failure output;
    # arbitrary nonzero exits never certify reproduction.
    failure = buggy.get('exit_code') == 1 and bool(re.search(r'FAILED|FAIL:|AssertionError|E\s+\w+(?:Error|Exception):', buggy.get('output', '')))
    success = fixed.get('exit_code') == 0 and bool(re.search(r'\b[1-9]\d* passed\b|\bOK\b', fixed.get('output', '')))
    if failure and success:
        return 'buggy_fails_fixed_passes'
    if buggy.get('exit_code') == 0:
        return 'bug_not_reproduced'
    if buggy.get('exit_code') == 1 and fixed.get('exit_code') == 1:
        return 'both_revisions_fail'
    return 'unconfirmed_failure'


def public_summary(report):
    """Allowlist provenance fields; never publish raw traces or local argv."""
    keys = ('project', 'bug_id', 'status', 'ready_for_prompt_review', 'upstream', 'buggy_commit',
            'fixed_commit', 'metadata_sha256', 'patch_sha256', 'sources', 'benchmark_python',
            'historical_input_verified', 'capture_commit_matches', 'license_artifacts',
            'test_files', 'source_import_verified', 'deviations')
    cases = []
    for case in report['cases']:
        exported = {key: case[key] for key in keys if key in case}
        exported['test_outcomes'] = {name: {key: run[key] for key in ('exit_code', 'timeout', 'output_sha256', 'latency_ms')}
                                     for name, run in case.get('fresh_runs', {}).items()}
        cases.append(exported)
    return {'version': report['version'], 'created_at': report['created_at'],
            'benchmark_revision': report['benchmark_revision'], 'selection': report['selection'],
            'capture_commit_counts': report['capture_inventory']['counts'], 'cases': cases,
            'previous_attempts': report.get('previous_attempts', []), 'notes': report['notes']}
