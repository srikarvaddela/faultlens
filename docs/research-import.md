# Offline research imports

FaultLens can inspect archived single-prompt/chain-of-prompt result CSVs without executing archived scripts, making model calls, or requiring upstream project checkouts.

From `backend`, with the virtual environment active:

```shell
python -m app.import_research /path/to/study.zip --name "Research archive"
```

Open **Research** in the workbench. Select a recorded run, project, and function-leakage label to inspect paired outcomes. Imports stay in the ignored local database; no archive, result files, model answers, or upstream source is bundled in the public repository. A ZIP content hash makes repeated imports idempotent. Each CSV retains a content hash, and identical file contents are flagged.

## Metric integrity

`single_localized`/`chain_localized` and legacy `single`/`chain` columns are imported as recorded booleans. These represent the archive's function-or-line localization criterion, not spectrum-based Top-1 or MRR. The importer does not re-score raw answers or independently validate ground truth. Missing outcomes are excluded from the paired accuracy denominator. Invalid boolean values or ambiguous CSV structure fail the import.

Only explicit `fn_leak` labels are used. Missing labels are **unknown**, never implicitly clean. Drift-step outcome flags are preserved when present. No significance test pools repeated observations, and overlapping or duplicate files are not automatically combined. Model names inferred from filenames are labeled as inferences; snapshots, latency, usage, and cost remain unavailable unless recorded separately.

## Deliberate limits

The importer reads whitelisted result fields only. It excludes raw answers, prompts, tracebacks, documents, and source. It does not execute Python in the archive, extract files, fetch repositories, or infer new leakage labels. Ground-truth reconstruction, evidence audits, stricter answer scoring, and live inference are later integrations. Schema versions, pairing across repeated passes, and original prompt variants must be defined before claiming the original study has been fully reproduced.
