import math

import pytest

from app.catalog import CATALOG
from app.evaluation import evaluate, execute_tests, rank_lines, summarize


@pytest.mark.parametrize("bug", CATALOG, ids=[bug["id"] for bug in CATALOG])
def test_each_fixture_reproduces_failures_and_fix_passes(bug):
    outcomes = execute_tests(bug)
    assert any(not test["passed"] for test in outcomes)
    assert any(test["passed"] for test in outcomes)
    fixed = {**bug, "source": bug["fixed_source"]}
    assert all(test["passed"] for test in execute_tests(fixed))


def test_ochiai_and_tarantula_known_coverage():
    tests = [
        {"passed": False, "covered_lines": [2, 3]},
        {"passed": False, "covered_lines": [2, 3]},
        {"passed": True, "covered_lines": [2, 4]},
    ]
    ochiai = {candidate["line"]: candidate for candidate in rank_lines(tests, "ochiai")}
    tarantula = {candidate["line"]: candidate for candidate in rank_lines(tests, "tarantula")}
    assert ochiai[3]["score"] == 1
    assert ochiai[2]["score"] == pytest.approx(2 / math.sqrt(6))
    assert tarantula[3]["score"] == 1
    assert tarantula[2]["score"] == 0.5
    assert ochiai[4]["score"] == 0


def test_ties_use_worst_rank_without_line_number_advantage():
    tests = [{"passed": False, "covered_lines": [9, 2]}, {"passed": True, "covered_lines": [9, 2]}]
    candidates = rank_lines(tests, "ochiai")
    assert [candidate["line"] for candidate in candidates] == [2, 9]
    assert all(candidate["rank"] == 2 for candidate in candidates)


def test_all_passing_tests_produce_zero_scores():
    for method in ("ochiai", "tarantula"):
        assert rank_lines([{"passed": True, "covered_lines": [2]}], method)[0]["score"] == 0


def test_ground_truth_does_not_change_rankings():
    bug = CATALOG[0]
    original = evaluate(bug, "ochiai")
    changed_truth = evaluate({**bug, "fault_line": 999}, "ochiai")
    assert original["candidates"] == changed_truth["candidates"]
    assert original["source_sha256"] == changed_truth["source_sha256"]
    assert original["evidence_sha256"] == changed_truth["evidence_sha256"]
    assert changed_truth["fault_rank"] is None
    assert changed_truth["reciprocal_rank"] == 0


def test_summary_uses_case_denominator_and_real_ranks():
    summary = summarize([
        {"top1": True, "top3": True, "reciprocal_rank": 1.0, "duration_ms": 10},
        {"top1": False, "top3": True, "reciprocal_rank": 0.5, "duration_ms": 20},
    ])
    assert summary == {"cases": 2, "top1": 0.5, "top3": 1, "mrr": 0.75, "total_duration_ms": 30}
