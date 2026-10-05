import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

METHODS = {
    "ochiai": {"id": "ochiai", "name": "Ochiai", "description": "Normalizes failing coverage by total line coverage."},
    "tarantula": {"id": "tarantula", "name": "Tarantula", "description": "Compares the fraction of failing and passing tests covering a line."},
}
RUNNER = Path(__file__).with_name("runner.py")


def execute_tests(bug):
    evidence = {key: bug[key] for key in ("source", "module", "function", "tests")}
    process = subprocess.run(
        [sys.executable, "-I", str(RUNNER)], input=json.dumps(evidence),
        capture_output=True, text=True, timeout=10, check=True,
    )
    return json.loads(process.stdout)


def rank_lines(tests, method):
    """Only coverage and pass/fail enter ranking; ground truth is excluded."""
    if method not in METHODS:
        raise ValueError("Unknown method")
    total_failed = sum(not test["passed"] for test in tests)
    total_passed = len(tests) - total_failed
    lines = sorted({line for test in tests for line in test["covered_lines"]})
    candidates = []
    for line in lines:
        failed = sum(not test["passed"] and line in test["covered_lines"] for test in tests)
        passed = sum(test["passed"] and line in test["covered_lines"] for test in tests)
        if method == "ochiai":
            denominator = math.sqrt(total_failed * (failed + passed))
            score = failed / denominator if denominator else 0.0
        else:
            fail_ratio = failed / total_failed if total_failed else 0.0
            pass_ratio = passed / total_passed if total_passed else 0.0
            score = fail_ratio / (fail_ratio + pass_ratio) if fail_ratio + pass_ratio else 0.0
        candidates.append({"line": line, "score": score, "failed_covered": failed, "passed_covered": passed})
    candidates.sort(key=lambda candidate: (-candidate["score"], candidate["line"]))
    # Worst position within a tie. Line-number sorting never earns extra accuracy.
    for candidate in candidates:
        candidate["rank"] = sum(
            other["score"] > candidate["score"] or math.isclose(other["score"], candidate["score"], rel_tol=1e-12, abs_tol=1e-12)
            for other in candidates
        )
    return candidates


def evaluate(bug, method):
    started = time.perf_counter()
    tests = execute_tests(bug)
    candidates = rank_lines(tests, method)
    truth = next((candidate for candidate in candidates if candidate["line"] == bug["fault_line"]), None)
    rank = truth["rank"] if truth else None
    return {
        "bug_id": bug["id"], "title": bug["title"], "method": method,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "tests": tests, "candidates": candidates, "fault_rank": rank,
        "top1": rank is not None and rank <= 1,
        "top3": rank is not None and rank <= 3,
        "reciprocal_rank": 1 / rank if rank else 0.0,
        "source_sha256": hashlib.sha256(bug["source"].encode()).hexdigest(),
        "evidence_sha256": hashlib.sha256(json.dumps({key: bug[key] for key in ("source", "tests")}, sort_keys=True).encode()).hexdigest(),
    }


def summarize(results):
    count = len(results)
    return {
        "cases": count,
        "top1": sum(result["top1"] for result in results) / count if count else 0,
        "top3": sum(result["top3"] for result in results) / count if count else 0,
        "mrr": sum(result["reciprocal_rank"] for result in results) / count if count else 0,
        "total_duration_ms": round(sum(result["duration_ms"] for result in results), 2),
    }
