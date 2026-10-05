"""Execute ONLY packaged fixtures in a short-lived child process.

This is process isolation for predictable trusted fixtures, NOT a security sandbox.
Never expose source upload or execute arbitrary repositories using this runner.
"""
import json
import math
import sys
import time


def matches(actual, expected):
    if isinstance(expected, (float, int)) and isinstance(actual, (float, int)):
        return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
    return actual == expected


def collect(bug):
    namespace = {}
    exec(compile(bug["source"], bug["module"], "exec"), namespace)
    function = namespace[bug["function"]]
    results = []
    for case in bug["tests"]:
        lines = set()

        def trace(frame, event, arg):
            if event == "line" and frame.f_code.co_filename == bug["module"]:
                lines.add(frame.f_lineno)
            return trace

        started = time.perf_counter()
        actual = None
        error = None
        sys.settrace(trace)
        try:
            actual = function(*case["args"])
            passed = matches(actual, case["expected"])
        except Exception as exc:
            passed = False
            error = f"{type(exc).__name__}: {exc}"
        finally:
            sys.settrace(None)
        results.append({
            "name": case["name"], "passed": passed, "expected": case["expected"],
            "actual": actual, "error": error, "covered_lines": sorted(lines),
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        })
    return results


if __name__ == "__main__":
    print(json.dumps(collect(json.load(sys.stdin))))
