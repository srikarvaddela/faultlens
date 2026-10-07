from copy import deepcopy
import json
import pytest

from app.evidence_ablation import transform
from app.real_prompting import prepare, verify
from app.validate_real_cases import copy_regression_assets
from test_real_prompting import bundle


def test_type_only_evidence_never_copies_messages_paths_or_unknown_class_names():
    raw = {'fresh_failing_test_output': 'File "/private/name.py", line 77, in secret_function\nE   AttributeError: secret_function at /private/name.py\ncustom.SecretError: private message\nFAILED tests/private_test.py\n'}
    reduced = transform(raw, 'exception_type_only')
    assert reduced['exception_types'] == ['AttributeError']
    assert all(value not in json.dumps(reduced) for value in ('/private', '77', 'secret_function', 'SecretError', 'private_test'))
    assert transform({'fresh_failing_test_output': 'custom.Error: unknown'}, 'exception_type_only')['extraction_status'] == 'unknown'
    assert transform(raw, 'fresh_regression_output') == raw


def test_conditions_share_source_oracle_and_parent_but_have_different_evidence():
    item = bundle()
    full = prepare(item)
    reduced = prepare(item, evidence_mode='exception_type_only')
    assert full['source_sha256'] == reduced['source_sha256']
    assert full['oracle_sha256'] == reduced['oracle_sha256']
    assert full['evidence_parent_sha256'] == reduced['evidence_parent_sha256']
    assert full['evidence_sha256'] != reduced['evidence_sha256']
    verify(reduced, item)
    wrong_parent = deepcopy(item)
    wrong_parent['evidence']['fresh_failing_test_output'] = 'ValueError: changed'
    with pytest.raises(ValueError, match='registered transform'):
        verify(reduced, wrong_parent)
    withdrawn = {**item, 'status': 'excluded', 'reason': 'Withdrawn missing fixture'}
    with pytest.raises(ValueError, match='Withdrawn'):
        verify(full, withdrawn)


def test_new_regression_fixture_is_transplanted_to_both_variants(tmp_path, monkeypatch):
    from app import validate_real_cases
    blobs = {'fixed:tests/test_case.py': b'assert True', 'fixed:tests/new_fixture.json': b'{"value":1}'}
    def fake_git(repo, *args):
        return b'tests/test_case.py\ntests/new_fixture.json\n' if args[0] == 'diff' else blobs[args[1]]
    monkeypatch.setattr(validate_real_cases, 'git', fake_git)
    buggy = copy_regression_assets(tmp_path, {'test_file': 'tests/test_case.py'}, 'buggy', 'fixed', tmp_path / 'buggy')
    fixed = copy_regression_assets(tmp_path, {'test_file': 'tests/test_case.py'}, 'buggy', 'fixed', tmp_path / 'fixed')
    assert buggy == fixed
    assert (tmp_path / 'buggy/tests/new_fixture.json').read_bytes() == (tmp_path / 'fixed/tests/new_fixture.json').read_bytes()
