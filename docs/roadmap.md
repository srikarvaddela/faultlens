# Milestones

## 1 — Reproducible workbench

- [x] Original Python fixtures, real test execution, and fixed-source validation
- [x] Ochiai/Tarantula ranking with conservative ties
- [x] React interface, code view, test evidence, and rankings
- [x] Saved experiment comparisons and JSON export
- [x] Backend tests, desktop/mobile browser checks, and CI configuration
- [x] Setup and methodology documentation

## 2 — Reliable experiment infrastructure

- [x] Durable worker with job states, bounded retries, cancellation, and recovery
- [ ] Database migrations and validated PostgreSQL deployment
- [x] Shared evidence collection across methods with separate ranking timings
- [ ] Authentication and per-user experiment ownership
- [ ] Resource limits, observability, and deployment smoke checks

## 3 — Live AI comparisons

- [x] Local Ollama integration; remote providers remain optional future work
- [x] Versioned single-prompt and multi-step plan templates with live execution
- [x] Strict ranking-output parser
- [x] Persisted local inference calls and parse-failure accounting
- [x] Native token usage, latency, and bounded local generation
- [ ] Remote-provider cost accounting and budget caps
- [x] Frozen input/response transcripts for local calls
- [x] Checkpointed curated benchmark runner and measured local model report
- [ ] Validated leakage-controlled real-world prompts

## 4 — Real-world benchmark

- [ ] Document benchmark provenance, licenses, and execution isolation
- [ ] Reproduce real bugs and retain environment manifests
- [ ] Predefine datasets, metrics, exclusions, and baselines
- [ ] Report paired results and uncertainty without cherry-picking
- [ ] Publish a demo, reproducible report, and evidence-backed resume bullets
