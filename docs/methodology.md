# Evaluation methodology v1.1

## Dataset

Six original Python defects, five tests each, covering arithmetic, indexing, boundary conditions, logic, and whitespace handling. Every buggy fixture has both passing and failing tests. Its corrected source passes all provided tests. These examples are not a real-world benchmark, do not derive from BugsInPy, and cannot establish general model or tool accuracy.

## Evidence

Each test records pass/fail, expected and actual output or exception, covered line numbers, and duration. Lines are counted once per test even if executed repeatedly. Executing a module definition is excluded: tracing begins when the fixture function is called. Both baselines include all lines executed by at least one test, including zero-score candidates.

For a line, `ef` is the number of failing tests covering it, `ep` the number of passing tests covering it, `F` the total failing tests, and `P` the total passing tests.

- Ochiai: `ef / sqrt(F * (ef + ep))`
- Tarantula: `(ef / F) / ((ef / F) + (ep / P))`

Undefined denominators produce zero scores. Scores are associations with test failure, not calibrated probabilities.

## Rankings and metrics

Scores are sorted descending, with line numbers providing a stable display order only. All lines tied at full precision (within a 1e-12 tolerance) receive the worst position of that group. A fault tied for positions 1–3 therefore has rank 3, misses Top-1, and contributes 1/3 to reciprocal rank. A fault missing from coverage has no rank and contributes zero.

Top-k is the fraction of selected bugs with ground-truth rank at most k. MRR is the mean reciprocal rank across selected bugs. Each method has its own denominator. Timing includes process startup, tests, and ranking; it is environment-dependent. Queued experiments collect evidence once per bug and reuse it for both methods. Exports distinguish evidence_duration_ms from ranking_duration_ms. total_duration_ms is a per-method sum including shared evidence; do not add it across methods to infer job wall time. The deprecated synchronous endpoint still collects evidence per method. These tiny fixtures do not support general latency claims.

## Leakage and reproducibility

Neither algorithm receives the known fault line or corrected source. A test mutates the ground-truth label and verifies the ranking remains identical. UI users can reveal the label after evaluation; visibility does not affect rankings. Source and evidence SHA-256 hashes, dataset/evaluator versions, selected methods, full-precision scores, test results, and timestamps are retained in exports.

Future LLM evaluation must separately control assertion messages, tracebacks, fixes, prompts, model snapshots, inference configuration, and costs. No such LLM experiment has been performed by this release.
