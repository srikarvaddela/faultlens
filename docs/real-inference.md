# Frozen real-case inference

Validated real cases can now enter the same durable Ollama queue as curated cases. The registry accepts frozen local inputs through an offline CLI; web requests can prepare only registered snapshots. It does not accept arbitrary repository execution or arbitrary source uploads.

## Prepare inputs

Run the [paired real-case validator](real-case-validation.md) first. Keep its `validation.json` and fresh `PROJECT-ID/buggy` directories together. From `backend`, run:

```powershell
.venv\Scripts\python -m app.freeze_real_cases C:/local/validation-new/validation.json
```

The freezer requires a successful buggy-fails/fixed-passes gate, import-origin verification, patch verification, and matching source/output hashes. It accepts CRLF-to-LF materialization only when the normalized bytes match the pinned Git blob. Any other source or failure-output change aborts registration. Complete files, fresh failure output, provenance, and a separate patch-location oracle are saved in the ignored local database. Failed controls and context exclusions are also registered with explicit reasons.

Open **Prompt lab**, choose **Validated real cases**, and prepare a plan. Inspect its first messages and caveats; run the single-versus-chain comparison with Ollama. Later messages depend on actual preceding responses. Results show exact file paths and original line numbers; saved calls can be reopened or exported locally. Curated plans continue to use their original prompts and context configuration.

The API supports `GET /api/real-cases` and `POST /api/real-prompt-plans` with `case_id` and `strategy` (`single` or `chain_evidence`). Existing `/api/ollama/runs`, cancellation, retry-as-new-run, and transcript export apply to real plans too.

## Run a batch

With API, worker, and local Ollama running, from the repository root:

```shell
python scripts/benchmark_real.py --model llama3.2:1b --output C:/local/real-batch.json --public-summary C:/local/real-measurements.json
```

This takes a selection snapshot of the registered cases, retains exclusions, and runs one comparison for every ready case. A comparison makes four calls. Existing output resumes known run IDs and never silently replays uncertain submissions. The runner rejects pooled output when model digest, Ollama version, or options differ. Full batch output is private; the optional measurement export omits source, traces, exact message text, response text, reasons, package inventories, and machine paths.

If multiple frozen snapshots of the same bug are registered, the runner stops rather than treating them as independent cases. Choose one per bug explicitly with `--case-ids ID1,ID2,...`. Resuming an existing batch preserves its original selection.

## Context, parsing, and scoring

Real plans now also support [exception-type-only evidence ablation](evidence-ablation.md). New freezing requires corrected validator version 1.1.0 and matching regression assets. API/worker checks block superseded snapshots; historical records remain readable with warnings. The [corrected ablation](benchmarks/real-evidence-ablation.md) supersedes the earlier Cookiecutter measurements.

Real plans request 32K context and 256 output tokens, with seed 42 and temperature zero. A conservative UTF-8-byte-count preflight reserves space for intermediate responses and output; it is an estimate, not an exact tokenizer count. Every materialized call is checked again before sending. Complete files exceeding the budget are excluded. There is no ground-truth-centered source cropping. Native prompt token counts are retained. [Ollama's context guidance](https://docs.ollama.com/context-length) describes allocated context inspection and memory tradeoffs.

Final structured output includes an exact file name from the supplied files, an integer line within that particular file, and a reason. The parser rejects unknown files, out-of-range or boolean lines, duplicate file/line pairs, malformed JSON, and extra fields. Ollama's JSON schema constrains generation; the application parser still validates every final answer. See [structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

Ground truth stays in a separate scoring field and is never included in rendered messages or provider schemas. The oracle contains removed old-file lines and explicitly marked anchors for purely additive changes. Rank is the first candidate matching any oracle file/line; invalid or missing rankings score zero. Reasons are retained for inspection but are not semantically graded.

The file set is selected using the benchmark patch. This supplies oracle-assisted file knowledge and makes the task file-conditioned. Failure output can expose fault clues. Results are not repository-wide localization, certified leakage-free evidence, a reproduction of the historical university experiment, or a replacement for its recorded scores.

## Reproducibility and limits

The worker checks frozen source/evidence/oracle hashes, numbered source, prompt version, and first messages before inference. Every exact request is saved before sending; responses and available token/timing metadata are persisted afterward. Model digest and Ollama version are checked between calls. Lease renewal, cooperative cancellation, bounded generation, and explicit retry behavior are shared with curated inference. Worker restarts do not silently replay uncertain calls.

Raw input/output stays local. Public summaries provide hashes for audit linkage and measurements, not full independent transcript reproduction. To independently reproduce the run, obtain upstream pinned source, reproduce the regression under an inspectable environment, and freeze new failure evidence; output may differ. Current validation reuses existing WSL environments and carries documented deviations. The measured baseline and all exclusions are in the [first comparison report](benchmarks/real-ollama-comparison.md).
