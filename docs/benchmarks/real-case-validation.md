# Real-case validation results

Six cases were selected before fresh reproduction: the same cases used for earlier capture spot checks, including missing-function and runner-failure controls. This is an input-readiness audit, not an LLM accuracy benchmark.

BugsInPy revision: `11c5f1eea954a42132cfd06bf257766a7963e0fd`. The [machine-readable provenance summary](real-case-validation.json) includes pinned buggy/fixed revisions, source and test hashes, patch-derived targets, license links, outcomes, setup adjustments, and earlier attempt statuses.

## Findings

All **199 archived capture commit IDs** match the corresponding BugsInPy buggy revision. A matching ID does not prove that the archived trace came from that source or that a historical model received that exact input.

| Case | Fresh buggy test | Fresh fixed test | Readiness |
|---|---|---|---|
| Black #1 | Fails | Passes | Ready for prompt review |
| HTTPie #3 | Fails | Passes | Ready for prompt review |
| FastAPI #16 | Fails | Passes | Ready for prompt review |
| Cookiecutter #1 | Fails | Passes | Ready for prompt review with documented tox-to-pytest adjustment |
| Black #3 | Fails | Passes | Ready for prompt review; source change is at module scope |
| FastAPI #14 | Fails | Fails | Excluded from ready cases |

Every selected case's old patch context matches the pinned buggy file, and applying that patch reproduces the complete corresponding fixed file. Import probes resolve to fresh source copies in both variants. The same fixed-revision regression test files run on each pair. Five cases pass the reproduction gate; none has yet received a new real-case model call.

FastAPI #14 fails in both variants with a `lifespan_middleware` attribute error. That environment/API incompatibility prevents this run from distinguishing the benchmark bug from a setup problem. Its nonzero exit is not counted as successful bug reproduction.

Black #3's patch changes a decorator option at module scope. An absent function label is appropriate for this shape; future scoring needs a source-line or file-aware oracle rather than guessing a function name from a diff header. Cookiecutter #1 now reproduces with direct pytest, although its earlier capture had a missing tox runner. The new failure is fresh evidence, not retroactive certification of that old capture.

## Limits and next input gate

Existing WSL Python environments were reused, with package inventories and actual Python versions saved locally. They differ from benchmark-exact environments. Black needs a generated inert version constant and test package marker; documentation symlinks are omitted. Pytest `addopts` is cleared, and Cookiecutter's tox setup is replaced by a selected pytest target. Earlier setup failures are retained in three prior attempt summaries; they are not silently discarded.

This selected set does not estimate reproduction success across BugsInPy. The 199-case check covers commit identities only; fresh tests cover six cases. No historical research score or leakage label was changed. Full private logs, paths, and inventories remain local and can be inspected in the app's Research panel.

Real-case inference remains gated on freezing an appropriate source context and fresh evidence, reviewing clues/leakage, and defining file/line scoring for additive and module-level changes. The existing model queue continues to accept curated fixtures. See [validator setup and methodology](../real-case-validation.md).
