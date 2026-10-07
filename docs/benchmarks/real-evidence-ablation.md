# Corrected real-case evidence ablation

This batch compares full fresh failure output with exception-type-only evidence on the same three eligible cases. Each condition runs a single prompt and a three-step chain: **24 model calls**, **12 final rankings**, and **11 valid finals**. All calls completed; one final was rejected for duplicate file/line candidates. Invalid rankings score zero and are not repaired.

Model: `llama3.2:1b`, digest `baf6a787fdffd633537aa2eb51cfd54cb93ff08e28040095462bb63daf552878`, Ollama `0.35.1`. Settings: seed 42, temperature 0, 256 output tokens, requested 32,768-token context. Prompts: `faultlens-real-prompts-1.1.0`. Transform: `exception-type-evidence-1.0.0`.

The [measurement export](real-evidence-ablation.json) records selection, conditions, hashes, runtime identity, counts, timing, parser outcomes, and ranks. Raw traces and responses stay local.

## Validation correction

The initial Cookiecutter run was confounded. The fixed commit adds `tests/test-generate-context/non_ascii.json`, but the first validator copied only regression test code into the buggy workspace. Its `FileNotFoundError` was a missing-fixture failure, not the intended encoding regression. The old patch-location hit happened to land on the same line without establishing correct reproduction.

The corrected validator copies changed regression assets into both variants and records their hashes. Cookiecutter uses the same recorded ASCII locale (`ANSI_X3.4-1968`) in both variants, with UTF-8 stdout. The fixture is present, the buggy implementation encounters `UnicodeDecodeError` wrapped as `ContextDecodingException`, and the fixed revision passes. See the [corrected source and asset ledger](real-case-validation-corrected.json).

Earlier Cookiecutter results are superseded. Their requests, responses, numeric scores, and the first 24-call ablation attempt remain available for audit and are excluded from this corrected batch. Retired snapshots are blocked from new inference; saved runs display a validation warning. Prior public reports retain original measurements with a correction notice.

## Paired design

Each case has identical complete buggy files, patch-location oracle, parent failure output, model digest, and settings across conditions. The runner verifies those hashes and that the server returned the requested condition. File selection remains oracle-assisted; this is localization within supplied changed files.

Reduced evidence contains only built-in exception names found in anchored exception headers. It never copies messages, paths, frames, line numbers, test names, or source excerpts. Unrecognized custom classes yield unknown status. Here the types are `AttributeError` for HTTPie and FastAPI, and `UnicodeDecodeError` for Cookiecutter. A recognized type can be a cause in a chained traceback rather than the final wrapper.

Order alternates by eligible case: HTTPie full first, FastAPI type-only first, Cookiecutter full first. Single precedes chain within each condition. Three cases do not give perfectly balanced ordering. Oversized Black files and the both-revisions-fail FastAPI #14 control remain excluded. The eligible set stays fixed across conditions.

## Outcomes

| Case | Full / single | Type-only / single | Full / chain | Type-only / chain |
|---|---:|---:|---:|---:|
| HTTPie #3 | Miss | Miss | Miss | Miss |
| FastAPI #16 | 2 | 2 | 1 | Miss |
| Cookiecutter #1 | Invalid: duplicate location | Miss | Miss | Miss |

Ranks measure the first candidate matching a removed old-file line or marked insertion anchor.

| Condition / strategy | Top-1 | Top-3 | Mean reciprocal rank | Valid finals |
|---|---:|---:|---:|---:|
| Full / single | 0/3 | 1/3 | 0.1667 | 2/3 |
| Type-only / single | 0/3 | 1/3 | 0.1667 | 3/3 |
| Full / chain | 1/3 | 1/3 | 0.3333 | 3/3 |
| Type-only / chain | 0/3 | 0/3 | 0.0000 | 3/3 |

All six chain step-2 responses reached the output limit; actual truncated text was carried forward. No final response was truncated. Reasons were not semantically graded.

## Interpretation

FastAPI's chain loses its hit when the trace is reduced to exception types. This demonstrates evidence sensitivity in this run. It does not isolate target-name leakage: the transform also removes legitimate diagnostic context and changes prompt length. Source and oracle-selected files still contain clues; type-only evidence is not certified leakage-free.

There are three independent bugs and one run per condition with a small local model. Conditions/strategies are repeated measurements of those bugs, not twelve independent cases. No significance or broad improvement claim is made. Loading, cache reuse, input length, and ordering limit timing comparisons. The main engineering outcome is a reproducible ablation and a validation check that caught a misleading success.

Reproduce using the [evidence ablation workflow](../evidence-ablation.md).
