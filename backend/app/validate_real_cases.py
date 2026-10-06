"""Validate pinned research cases without executing scripts from the archive.

Fresh tests run in new workspace directories using explicitly selected WSL
Python environments. They are subprocesses, not a security sandbox.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import time
import zipfile

from .database import initialize_database, SessionLocal, ResearchImport
from .real_validation import VERSION, info, sha256, patch_sections, check_source, reproduction_status, public_summary

CASES = [('black', 1), ('httpie', 3), ('fastapi', 16), ('cookiecutter', 1), ('black', 3), ('fastapi', 14)]


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, timeout=60).stdout


def safe_path(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe source path')
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Source path escapes workspace')
    return target


def extract_revision(repo, revision, directory):
    if directory.exists():
        raise ValueError('Use a fresh output directory; existing source trees are never reset')
    data = git(repo, 'archive', '--format=zip', revision)
    directory.mkdir(parents=True)
    omitted = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for item in archive.infolist():
            target = safe_path(directory, item.filename)
            if ((item.external_attr >> 16) & 0o170000) == 0o120000:
                if item.filename.startswith('docs/'):
                    omitted.append(item.filename)
                    continue
                raise ValueError('Symlink in source archive')
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(item))
    return omitted


def linux_path(path):
    absolute = str(path.resolve()).replace('\\', '/')
    if not re.match(r'^[A-Za-z]:/', absolute):
        raise ValueError('WSL runner requires a Windows drive path')
    return '/mnt/' + absolute[0].lower() + absolute[2:]


def parse_recipe(recipe):
    tokens = shlex.split(recipe.strip())
    if len(tokens) < 2 or any(re.search(r'[;&|<>`$]', token) for token in tokens):
        raise ValueError('Test recipe must be a single explicit test command')
    if tokens[0] == 'pytest':
        return ['-m', 'pytest', *tokens[1:]], None
    if tokens[0] == 'python' and tokens[1:3] == ['-m', 'unittest']:
        return tokens[1:], None
    if tokens[0] == 'tox' and len(tokens) == 2 and tokens[1].startswith('tests/'):
        return ['-m', 'pytest', tokens[1]], 'Benchmark tox recipe replaced with direct pytest in the existing selected environment; no tox setup executed.'
    raise ValueError('Unsupported test recipe')


def capture_inventory(captures, benchmark):
    rows = []
    for path in sorted(captures.glob('*.json')):
        data = path.read_bytes()
        capture = json.loads(data)
        project, bug = str(capture.get('project', '')), str(capture.get('bug_id', ''))
        row = {'project': project, 'bug_id': bug, 'capture_sha256': sha256(data), 'status': 'invalid_identity'}
        if re.fullmatch(r'[A-Za-z0-9_-]+', project) and re.fullmatch(r'[0-9]+', bug):
            metadata_path = benchmark / 'projects' / project / 'bugs' / bug / 'bug.info'
            if metadata_path.exists():
                metadata = info(metadata_path.read_text())
                row['buggy_commit'] = metadata.get('buggy_commit_id')
                row['status'] = ('commit_unrecorded' if not capture.get('buggy_commit') else
                                 'commit_matches' if capture['buggy_commit'] == row['buggy_commit'] else 'commit_mismatch')
            else:
                row['status'] = 'benchmark_case_missing'
        rows.append(row)
    return {'rows': rows, 'counts': dict(Counter(row['status'] for row in rows)),
            'note': 'Commit identity audit only: matching metadata does not prove an archived failure or historical prompt input.'}


def wsl_run(directory, python, args):
    started = time.perf_counter()
    command = ['wsl', '-d', 'Ubuntu', '--cd', linux_path(directory), '--exec', 'timeout', '90s',
               'env', 'PYTHONNOUSERSITE=1', 'PYTHONDONTWRITEBYTECODE=1',
               'PYTHONPATH=' + linux_path(directory), python, *args]
    result = subprocess.run(command, capture_output=True, timeout=110)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    return {'argv': command, 'exit_code': result.returncode, 'timeout': result.returncode == 124,
            'output': output, 'output_sha256': sha256(output.encode()), 'latency_ms': round((time.perf_counter()-started)*1000, 2)}


def validate_case(project, bug_id, args, root):
    benchmark = args.benchmark / 'projects' / project
    folder = benchmark / 'bugs' / str(bug_id)
    bug_info_data = (folder / 'bug.info').read_bytes()
    metadata = info(bug_info_data.decode())
    repo = args.repos / (project + '_repo')
    remote = git(repo, 'remote', 'get-url', 'origin').decode().strip()
    expected = info((benchmark / 'project.info').read_text())['github_url']
    normalize = lambda url: url.rstrip('/').removesuffix('.git').lower()
    if normalize(remote) != normalize(expected):
        raise ValueError('Local repository origin does not match benchmark metadata')
    buggy, fixed = metadata['buggy_commit_id'], metadata['fixed_commit_id']
    if any(not re.fullmatch(r'[0-9a-f]{40}', revision) for revision in (buggy, fixed)):
        raise ValueError('Full pinned commit hashes required')
    patch = (folder / 'bug_patch.txt').read_bytes()
    checked = [check_source(section, git(repo, 'show', f"{buggy}:{section['path']}"), git(repo, 'show', f"{fixed}:{section['path']}")) for section in patch_sections(patch.decode())]
    case = {'project': project, 'bug_id': str(bug_id), 'upstream': expected, 'buggy_commit': buggy,
            'fixed_commit': fixed, 'metadata_sha256': sha256(bug_info_data), 'patch_sha256': sha256(patch),
            'sources': checked, 'benchmark_python': metadata['python_version'], 'historical_input_verified': False,
            'status': 'static_only', 'fresh_runs': {}, 'deviations': [], 'test_files': []}
    license_names = [name for name in git(repo, 'ls-tree', '--name-only', buggy).decode().splitlines() if name.upper().startswith(('LICENSE', 'COPYING'))]
    case['license_artifacts'] = [{'path': name, 'sha256': sha256(git(repo, 'show', f'{buggy}:{name}')),
        'url': expected.rstrip('/') + f'/blob/{buggy}/{name}'} for name in license_names]
    capture_path = args.captures / f'{project}_{bug_id}.json'
    if capture_path.exists():
        capture_bytes = capture_path.read_bytes()
        capture = json.loads(capture_bytes)
        case['capture_sha256'] = sha256(capture_bytes)
        case['capture_commit_matches'] = capture.get('buggy_commit') == buggy
        case['archive_claimed_reproduced'] = capture.get('reproduced', type(capture.get('exit')) is int and capture['exit'] != 0)
    else:
        case['capture_commit_matches'] = None
    if not all(source['patch_verified'] for source in checked):
        case['status'] = 'source_mismatch'
        return case
    case_root = root / f'{project}-{bug_id}'
    recipe = (folder / 'run_test.sh').read_text().strip()
    argv, deviation = parse_recipe(recipe)
    case['benchmark_recipe'] = recipe
    if deviation:
        case['deviations'].append(deviation)
    if argv[:2] == ['-m', 'pytest']:
        argv += ['-o', 'addopts=']
        case['deviations'].append('Clear configured pytest addopts for the explicitly selected regression test; coverage plugins are not required.')
    python = args.environments.rstrip('/') + f'/bug_{project}/bin/python'
    for variant, revision in [('buggy', buggy), ('fixed', fixed)]:
        directory = case_root / variant
        omitted = extract_revision(repo, revision, directory)
        if omitted:
            case['deviations'].append({'variant': variant, 'omitted_documentation_symlinks': omitted})
        for name in metadata['test_file'].split(';'):
            data = git(repo, 'show', f'{fixed}:{name}')
            target = safe_path(directory, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if variant == 'buggy':
                case['test_files'].append({'path': name, 'revision': fixed, 'sha256': sha256(data)})
        # Upstream black uses a packaging-generated version module. Generate only
        # that inert constant, never execute setup.py or archived helper scripts.
        if project == 'black':
            version_file = directory / '_black_version.py'
            if not version_file.exists():
                version_file.write_text('version = "19.10b0"\n', encoding='utf-8')
                if variant == 'buggy':
                    case['deviations'].append('Generated inert _black_version.py constant 19.10b0 instead of invoking packaging; source otherwise pinned.')
            package_marker = directory / 'tests' / '__init__.py'
            if not package_marker.exists():
                package_marker.write_text('', encoding='utf-8')
                if variant == 'buggy':
                    case['deviations'].append('Added empty tests/__init__.py to prevent installed tests package shadowing the pinned regression tests.')
        if variant == 'buggy':
            case['environment'] = wsl_run(directory, python, ['--version'])
            case['installed_packages'] = wsl_run(directory, python, ['-m', 'pip', 'freeze'])
        modules = [s['path'].removesuffix('.py').replace('/', '.').removesuffix('.__init__') for s in checked if s['path'].endswith('.py')]
        probe = 'import importlib.util,json; print(json.dumps({m:importlib.util.find_spec(m).origin for m in ' + repr(modules) + '}))'
        origin = wsl_run(directory, python, ['-c', probe])
        case.setdefault('import_origins', {})[variant] = origin
        try:
            paths = json.loads(origin['output'])
            verified = origin['exit_code'] == 0 and all(value == linux_path(directory / s['path']) for s, value in zip([s for s in checked if s['path'].endswith('.py')], paths.values()))
        except (ValueError, TypeError):
            verified = False
        case.setdefault('source_import_verified', {})[variant] = verified
        case['fresh_runs'][variant] = wsl_run(directory, python, argv)
    case['status'] = reproduction_status(case['fresh_runs']['buggy'], case['fresh_runs']['fixed'])
    if not all(case['source_import_verified'].values()):
        case['status'] = 'source_import_unverified'
    # Fresh reproduction does not verify past prompts or certify absence of clues.
    case['ready_for_prompt_review'] = case['status'] == 'buggy_fails_fixed_passes'
    return case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', type=Path, required=True)
    parser.add_argument('--repos', type=Path, required=True)
    parser.add_argument('--captures', type=Path, required=True)
    parser.add_argument('--environments', required=True, help='Explicit WSL conda environment root')
    parser.add_argument('--output', type=Path, required=True, help='Fresh local output directory; includes private logs')
    parser.add_argument('--import-id', help='Attach results to this existing local research import')
    parser.add_argument('--public-summary', type=Path, help='Optional allowlisted provenance export without raw traces or local paths')
    parser.add_argument('--previous-report', type=Path, action='append', default=[], help='Retain prior attempts instead of hiding setup failures')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be a fresh directory')
    args.output.mkdir(parents=True)
    report = {'version': VERSION, 'created_at': datetime.now(timezone.utc).isoformat(),
              'benchmark_revision': git(args.benchmark, 'rev-parse', 'HEAD').decode().strip(),
              'selection': 'Six preselected capture-audit cases: black 1/3, httpie 3, fastapi 14/16, cookiecutter 1. Includes earlier unknown and environment-failure controls.',
              'cases': [], 'notes': ['Original research repositories are read only. Fresh copies use pinned commits and identical fixed-revision tests.',
                  'Existing WSL environments are reused, not benchmark-exact environments. Versions and package inventories are retained.',
                  'Fresh subprocesses are not a sandbox. No archive scripts, setup.sh, tox setup, or model calls run.',
                  'Buggy-fails/fixed-passes is a reproduction gate, not proof of historical prompt identity or leakage-free inputs.']}
    report['capture_inventory'] = capture_inventory(args.captures, args.benchmark)
    report['previous_attempts'] = []
    for path in args.previous_report:
        data = path.read_bytes()
        previous = json.loads(data)
        report['previous_attempts'].append({'report_sha256': sha256(data), 'created_at': previous['created_at'],
            'cases': [{'project': c['project'], 'bug_id': c['bug_id'], 'status': c['status']} for c in previous['cases']]})
    for project, bug_id in CASES:
        try:
            case = validate_case(project, bug_id, args, args.output)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            case = {'project': project, 'bug_id': str(bug_id), 'status': 'validation_error', 'error': str(exc), 'sources': [], 'fresh_runs': {}, 'ready_for_prompt_review': False}
        report['cases'].append(case)
        (args.output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f"{project} {bug_id}: {case['status']}", flush=True)
    if args.public_summary:
        args.public_summary.parent.mkdir(parents=True, exist_ok=True)
        args.public_summary.write_text(json.dumps(public_summary(report), indent=2) + '\n', encoding='utf-8')
    if args.import_id:
        initialize_database()
        with SessionLocal() as session:
            row = session.get(ResearchImport, args.import_id)
            if not row:
                raise ValueError('Research import not found')
            payload = deepcopy(row.payload)
            payload['real_validation'] = report
            row.payload = payload
            session.commit()


if __name__ == '__main__':
    main()
