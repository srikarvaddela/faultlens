import json
import zipfile

import pytest

from app.leakage import parse_captures, derive, attach_leakage
from app.research import read_archive


def capture(trace='File "app.py", line 20, in calculate', **changes):
    record = {'project': 'example', 'bug_id': 1, 'reproduced': True, 'exit': 1, 'error_message': 'ValueError: bad input', 'stack_trace': trace, **changes}
    return parse_captures({'example_1.json': json.dumps(record).encode()})[('example', '1')]


def row(**changes):
    return {'project': 'example', 'bug_id': '1', 'source': 'real', 'real_evidence': True, 'fn_leak': None, 'ground_truth': {'functions': ['calculate'], 'line': 20}, 'single': True, 'chain': False, **changes}


def test_positive_matches_have_inspectable_provenance():
    evidence = capture()
    result = derive(row(), evidence)
    assert result['fn_leak'] is True
    assert result['matches'][0]['function'] == 'calculate'
    assert 'in calculate' in result['matches'][0]['excerpt']
    assert result['historical_input_verified'] is False
    assert len(evidence['evidence_sha256']) == 64


def test_boundary_matching_and_case_handling():
    assert derive(row(), capture('in calculate_extra'))['fn_leak'] is False
    assert derive(row(), capture('in CALCULATE'))['fn_leak'] is True


@pytest.mark.parametrize('changes,reason', [
    ({'source': 'real_module_mutant'}, 'not_real_case'),
    ({'real_evidence': False}, 'placeholder_evidence'),
    ({'ground_truth': {'functions': [], 'line': 20}}, 'missing_function_ground_truth'),
    ({'ground_truth': {'functions': ['<module>'], 'line': 20}}, 'missing_function_ground_truth'),
    ({'audit_status': 'ambiguous_case_identity'}, 'ambiguous_case_identity'),
    ({'audit': {'flags': ['csv_raw_ground_truth_disagreement']}}, 'ground_truth_conflict'),
])
def test_unusable_case_metadata_stays_unknown(changes, reason):
    result = derive(row(**changes), capture())
    assert result['fn_leak'] is None
    assert result['reason'] == reason


def test_missing_and_unreproduced_captures_stay_unknown():
    assert derive(row(), None)['reason'] == 'missing_capture'
    assert derive(row(), capture(reproduced=False))['fn_leak'] is None
    assert derive(row(), capture(''))['fn_leak'] is None


def test_missing_runner_cannot_become_a_no_match_case():
    result = derive(row(), capture('bash: line 1: tox: command not found', error_message='Test failed (see trace)'))
    assert result['fn_leak'] is None
    assert result['reason'] == 'runner_unavailable'


def test_recorded_labels_are_never_overwritten():
    original = row(fn_leak=False)
    runs = [{'rows': [original]}]
    attach_leakage(runs, {'example_1.json': json.dumps({'project': 'example', 'bug_id': 1, 'exit': 1, 'error_message': 'calculate failed', 'stack_trace': 'trace'}).encode()})
    assert original['fn_leak'] is False
    assert original['derived_leakage']['fn_leak'] is True


def test_capture_schema_rejects_ambiguous_reproduction_status():
    with pytest.raises(ValueError):
        capture(reproduced='False')


def test_archive_import_keeps_strata_separate_and_hashes_evidence(tmp_path):
    path = tmp_path/'study.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('results_test.csv', 'project,bug_id,source,real_evidence,gt_function,single,chain\nexample,1,real,True,calculate,True,False\nexample,2,real,True,calculate,False,True\nexample,3,real,True,,True,True\n')
        for bug, trace in [(1, 'in calculate'), (2, 'in test_example'), (3, 'in calculate')]:
            z.writestr(f'real_errors/example_{bug}.json', json.dumps({'project':'example','bug_id':bug,'exit':1,'error_message':'Failure','stack_trace':trace}))
    report = read_archive(path)
    strata = report['runs'][0]['derived_strata']
    assert strata['match']['paired'] == strata['no_match']['paired'] == strata['unknown']['paired'] == 1
    assert strata['match']['single_accuracy'] == 1
    assert strata['no_match']['single_accuracy'] == 0
    assert report['leakage_summary']['historical_input_verified'] is False
    assert 'original_evidence' not in report['capture_evidence']['example_1.json']
