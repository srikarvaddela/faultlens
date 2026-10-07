# First real-case Ollama comparison

**Correction:** Cookiecutter's earlier failure was caused by a missing added regression fixture. Its results and this table's aggregate scores are superseded for research interpretation. Original measurements remain for audit. Use the [corrected evidence ablation](real-evidence-ablation.md), with matching assets and the intended encoding failure.

FaultLens ran one single-prompt versus three-step comparison for each eligible frozen real case. All **12 model calls completed**, and **six final rankings passed the strict file-and-line parser**. This is a small pipeline baseline, not evidence of a general improvement.

Model: `llama3.2:1b`, digest `baf6a787fdffd633537aa2eb51cfd54cb93ff08e28040095462bb63daf552878`, Ollama `0.35.1`. Both methods use temperature 0, seed 42, a 32,768-token requested context, and 256 output tokens per call. An Ollama running-model check observed an allocated context of 32,768. Versioned prompts are `faultlens-real-prompts-1.0.0`.

The [measurement export](real-ollama-comparison.json) retains selection decisions, source/evidence/oracle/plan hashes, exact-request and response hashes, model identity, native token counts, load timing, wall latency, parse outcomes, and ranks. Full private requests, source, traces, and responses remain in the local database and private batch file.

## Selection

| Preselected case | Decision |
|---|---|
| Black #1 | Excluded: complete file exceeds conservative context budget |
| HTTPie #3 | Included: paired regression reproduced and complete file fits |
| FastAPI #16 | Included: paired regression reproduced and complete file fits |
| Cookiecutter #1 | Included: paired regression reproduced with documented direct-pytest adjustment and complete file fits |
| Black #3 | Excluded: complete file exceeds conservative context budget |
| FastAPI #14 | Excluded: buggy and fixed revisions both fail |

No source windows were selected around known changed lines. Oversized files were excluded rather than cropped. The exclusion log includes all six selected cases, including the failed control; results use the three inference-eligible cases as their denominator.

## Measured outcomes

| Case | Single patch-location rank | Chain patch-location rank |
|---|---:|---:|
| HTTPie #3 | Miss | Miss |
| FastAPI #16 | 2 | 1 |
| Cookiecutter #1 | 3 | 2 |

| Method | Top-1 | Top-3 | Mean reciprocal rank | Valid finals |
|---|---:|---:|---:|---:|
| Single prompt | 0/3 | 2/3 | 0.2778 | 3/3 |
| Evidence-carrying chain | 1/3 | 2/3 | 0.5000 | 3/3 |

All three chain step-2 responses reached the 256-token output limit. Their actual truncated text was passed to step 3 and preserved. No final response was truncated. Candidate reasons were not semantically graded; a valid JSON response or matching source location does not establish correct reasoning.

## What the metric measures

This is **file-conditioned localization with oracle-assisted file selection**. The benchmark patch identifies which complete files to supply. It is not repository-wide file discovery. Patch text, fixed source, changed-line labels, and scoring oracles are not sent in model messages. Fresh test output can still disclose target names or lines, so this is not a leakage-controlled comparison or a reproduction of the archived study.

A candidate hits when its exact file and original line match any removed old-file line or an explicitly marked insertion anchor. Purely additive fixes use the old line immediately preceding insertion as a proxy; that anchor is not proof of a uniquely faulty executable statement. The score is therefore a **patch-location hit**, not the historical function-or-line metric. It should not be combined with curated single-fault metrics or archived accuracy tables.

Both methods receive the same complete buggy files and same frozen fresh failure output for each case. Windows Git archive materialization used CRLF: freezing verifies the original pinned source hash after CRLF-to-LF normalization, records the raw workspace hash, and rejects any other content change. No real model calls execute repository code.

This single run has only three eligible bugs. There is no significance test, confidence interval claiming study-level generalization, or model-selection claim. Single always precedes chain within a pair, and timing includes model loading/cache effects. Native token counts and timing are available in the export, but the ordering does not support a fair speed benchmark. No failed call was silently replayed.

See [real inference setup and guards](../real-inference.md) and the [source/reproduction audit](real-case-validation.md).
