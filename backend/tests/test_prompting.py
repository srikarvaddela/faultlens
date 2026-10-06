import json

import pytest

from app.prompting import prepare, render_step, parse_ranking


def test_plan_hashes_are_reproducible_without_ids_or_timestamps():
    first = prepare('FL-001', 'single', 'failure_details')
    second = prepare('FL-001', 'single', 'failure_details')
    assert first['id'] != second['id']
    assert first['plan_sha256'] == second['plan_sha256']
    assert first['first_messages_sha256'] == second['first_messages_sha256']
    assert 'fault_line' not in json.dumps(first)
    assert 'fixed_source' not in json.dumps(first)
    assert first['status'] == 'prepared_no_inference'


def test_chain_restates_evidence_only_for_carryover_strategy():
    original = prepare('FL-002', 'chain_original', 'failure_details')
    carried = prepare('FL-002', 'chain_evidence', 'failure_details')
    response = ['An index error occurred.']
    assert 'Original failure evidence:' not in render_step(original, 1, response)[1]['content']
    assert 'Original failure evidence:' in render_step(carried, 1, response)[1]['content']
    assert original['evidence_sha256'] == carried['evidence_sha256']
    assert original['first_messages_sha256'] == carried['first_messages_sha256']
    assert original['plan_sha256'] != carried['plan_sha256']
    assert 'An index error occurred.' in render_step(carried, 2, response + ['Check the middle pair.'])[1]['content']


def test_later_steps_require_actual_prior_responses():
    plan = prepare('FL-001', 'chain_evidence', 'failure_details')
    with pytest.raises(ValueError):
        render_step(plan, 1, [])
    with pytest.raises(ValueError):
        render_step(plan, 3, ['one', 'two', 'three'])


def test_exception_only_keeps_absence_of_exceptions_explicit():
    plan = prepare('FL-001', 'single', 'exception_only')
    assert plan['evidence']['exceptions'] == []
    assert 'failing_tests' not in plan['evidence']
    assert 'may provide no exception' in plan['evidence']['note']


@pytest.mark.parametrize('text,error', [
    ('not json', 'invalid_json'),
    ('{"candidates": []}', 'invalid_schema'),
    ('{"candidates": [{"line": true, "reason": "x"}]}', 'invalid_candidate'),
    ('{"candidates": [{"line": 999, "reason": "x"}]}', 'invalid_candidate'),
    ('{"candidates": [{"line": 2, "reason": "x"}, {"line": 2, "reason": "y"}]}', 'invalid_candidate'),
    ('{"candidates": [{"line": 2, "reason": ""}]}', 'invalid_candidate'),
])
def test_invalid_rankings_are_not_silently_accepted(text, error):
    result = parse_ranking(text, 4)
    assert result['valid'] is False
    assert result['error'] == error
    assert result['candidates'] == []


def test_valid_ranking_preserves_order_without_scoring_accuracy():
    result = parse_ranking('{"candidates":[{"line":3,"reason":"Wrong scaling"},{"line":2,"reason":"Boundary"}]}', 4)
    assert result['valid'] is True
    assert [row['line'] for row in result['candidates']] == [3, 2]
    assert 'accuracy' not in result
