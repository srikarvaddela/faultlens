# Local Ollama curated benchmark

Model: `llama3.2:1b`. Digest: `baf6a787fdffd633537aa2eb51cfd54cb93ff08e28040095462bb63daf552878`. Ollama: `0.35.1`.

Six original educational Python bugs, 3 repeats per bug, single prompt versus a three-step chain carrying failure evidence. Inputs use `failure_details`. Exact requests, responses, identities, hashes, and timings are in [the JSON export](llama3.2-1b-curated.json).

Generation options: `{"num_ctx": 4096, "num_predict": 256, "seed": 42, "temperature": 0}`. Both strategies receive the same frozen source and evidence for each paired run. Ground truth is used only after inference for scoring.

Inference implementation revision: `ebe2dc8dbf246bf2d1850df49cea53db31434a72`. Runner platform: `Windows-11-10.0.26200-SP0`. This records the API implementation revision; benchmark tooling is committed afterward. It does not capture a complete hardware/environment manifest.

## Results

| Strategy | Trials | Top-1 | Top-3 | MRR | Valid finals | Truncated calls | Input / output tokens | Wall / load seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| single | 18 | 0.0% | 50.0% | 0.1667 | 15/18 | 0 | 4749 / 1284 | 19.58 / 6.13 |
| chain_evidence | 18 | 0.0% | 66.7% | 0.2593 | 15/18 | 18 | 19497 / 7591 | 57.06 / 0.33 |

| Bug | Single fault ranks by repeat | Chain fault ranks by repeat |
|---|---|---|
| FL-001 | 3, 3, 3 | 2, 2, 2 |
| FL-002 | 3, 3, 3 | miss, miss, miss |
| FL-003 | 3, 3, 3 | 3, 3, 3 |
| FL-004 | invalid/unavailable, invalid/unavailable, invalid/unavailable | invalid/unavailable, invalid/unavailable, invalid/unavailable |
| FL-005 | miss, miss, miss | 2, 3, 3 |
| FL-006 | miss, miss, miss | 3, 3, 3 |

Completed model calls: 72/72 saved calls. Terminal run statuses: `{"completed": 18, "failed": 0, "cancelled": 0}`.

## Interpretation and limits

- All planned strategy trials are included in accuracy denominators; invalid or unavailable finals score zero. Parse validity is reported separately. No failed calls are silently retried.
- Repeats share seed 42 and temperature zero. They measure observed repeatability, not 18 independent bugs. No significance test or general accuracy claim is supported by six fixtures.
- Candidate rank checks the known faulty line only. Valid JSON and a correct line do not establish correct reasoning. Explanations were not semantically graded.
- Truncation counts any response with `done_reason=length`, including intermediate chain steps. Later steps receive the actual truncated text.
- Single runs precede chain runs within every pair. Native load time is included in wall latency; cache, loading, ordering, and local hardware confound speed comparisons. Summed latency covers model HTTP calls only, not evidence collection or queue time.
- These prompts and fixtures do not reproduce the archived university study or establish leakage-free real-world performance. This is an engineering baseline for the local inference pipeline.

## Reproduce

Start the native API, worker, and Ollama with the installed model, then run from the repository root:

```shell
python scripts/benchmark_ollama.py --model llama3.2:1b --repeats 3 --output benchmark-local.json
```

Use a new output path for a new batch. An existing file resumes known run IDs without replaying them. If submission completion is uncertain, the runner stops for reconciliation. Model output and timing may differ on another runtime or hardware.
