import pytest

from app.real_validation import patch_sections, check_source, reproduction_status, public_summary
from app.validate_real_cases import safe_path, parse_recipe, capture_inventory


def test_diff_oracle_maps_original_lines_and_verifies_fixed_source():
    old = b'def first():\n    return 1\n\ndef second():\n    return 2\n'
    fixed = b'def first():\n    return 3\n\ndef second():\n    if True:\n        pass\n    return 2\n'
    patch = 'diff --git a/module.py b/module.py\n--- a/module.py\n+++ b/module.py\n@@ -1,2 +1,2 @@\n def first():\n-    return 1\n+    return 3\n@@ -4,2 +4,4 @@\n def second():\n+    if True:\n+        pass\n     return 2\n'
    result = check_source(patch_sections(patch)[0], old, fixed)
    assert result['patch_verified']
    assert result['targets'] == [{'line': 2, 'kind': 'removed_line', 'function': 'first'},
                                 {'line': 4, 'kind': 'insertion_anchor', 'function': 'second'}]
    assert not check_source(patch_sections(patch)[0], old.replace(b'return 1', b'return 9'), fixed)['patch_verified']
    assert not check_source(patch_sections(patch)[0], old, fixed + b'new = 1\n')['patch_verified']


@pytest.mark.parametrize('buggy,fixed,status', [
    ({'exit_code': 1, 'output': 'FAILED tests/test_a.py - AssertionError'}, {'exit_code': 0, 'output': '1 passed'}, 'buggy_fails_fixed_passes'),
    ({'exit_code': 1, 'output': 'FAILED ImportError'}, {'exit_code': 0, 'output': '1 passed'}, 'environment_failure'),
    ({'exit_code': 1, 'output': 'FAILED'}, {'exit_code': 1, 'output': 'FAILED'}, 'both_revisions_fail'),
    ({'exit_code': 0, 'output': '1 passed'}, {'exit_code': 0, 'output': '1 passed'}, 'bug_not_reproduced'),
    ({'exit_code': 1, 'output': 'FAILED'}, {'exit_code': 0, 'output': '0 passed'}, 'unconfirmed_failure'),
    ({'exit_code': 124, 'timeout': True}, {'exit_code': 0, 'output': '1 passed'}, 'timeout'),
])
def test_nonzero_exit_and_setup_failures_never_certify_reproduction(buggy, fixed, status):
    assert reproduction_status(buggy, fixed) == status


def test_paths_and_shell_recipes_cannot_escape_or_execute_extra_commands(tmp_path):
    for path in ('../escape.py', '/absolute', 'C:/absolute', 'a\\b'):
        with pytest.raises(ValueError):
            safe_path(tmp_path, path)
    with pytest.raises(ValueError):
        parse_recipe('pytest tests/test_a.py; rm -rf somewhere')
    assert parse_recipe('pytest tests/test_a.py::test_case')[0] == ['-m', 'pytest', 'tests/test_a.py::test_case']


def test_commit_inventory_keeps_unknowns_and_conflicts(tmp_path):
    captures = tmp_path / 'captures'
    captures.mkdir()
    folder = tmp_path / 'benchmark/projects/example/bugs/1'
    folder.mkdir(parents=True)
    (folder / 'bug.info').write_text('buggy_commit_id="a"')
    (captures / 'one.json').write_text('{"project":"example","bug_id":1,"buggy_commit":"b"}')
    (captures / 'two.json').write_text('{"project":"example","bug_id":2}')
    result = capture_inventory(captures, tmp_path / 'benchmark')
    assert result['counts'] == {'commit_mismatch': 1, 'benchmark_case_missing': 1}


def test_public_export_excludes_private_traces_and_machine_paths():
    report = {'version': '1', 'created_at': 'now', 'benchmark_revision': 'abc', 'selection': 'controls',
        'capture_inventory': {'counts': {'commit_matches': 1}, 'rows': [{'capture_sha256': 'private'}]},
        'notes': [], 'cases': [{'project': 'example', 'bug_id': '1', 'status': 'both_revisions_fail',
        'fresh_runs': {'buggy': {'exit_code': 1, 'timeout': False, 'output_sha256': 'hash', 'latency_ms': 2,
        'output': 'private research trace', 'argv': ['C:/private/workspace']}},
        'installed_packages': {'output': 'private package inventory'}}]}
    exported = str(public_summary(report))
    assert 'private' not in exported
    assert 'both_revisions_fail' in exported
    assert 'output_sha256' in exported


def test_import_upgrade_retains_separate_validation_ledger(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database import Base, ResearchImport
    from app.research import save_import
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ResearchImport(id='same-archive', name='study', created_at='now',
            payload={'importer_version': 'old', 'real_validation': {'cases': ['audit']}}))
        session.commit()
        save_import(session, {'id': 'same-archive', 'importer_version': 'new', 'runs': []})
        assert session.get(ResearchImport, 'same-archive').payload['real_validation'] == {'cases': ['audit']}
    engine.dispose()
