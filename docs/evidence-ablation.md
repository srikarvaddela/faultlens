# Evidence ablation workflow

Real plans support `fresh_regression_output` (default) and `exception_type_only`. In Prompt lab, choose **Validated real cases**, select **Real failure evidence**, and prepare the plan. First messages show actual transformed input; saved history identifies the condition.

The type-only transform uses a fixed built-in exception-name allowlist and anchored exception headers. It retains no free-form trace text. Unknown custom classes remain unknown. Source, oracle, and parent evidence hashes link conditions; a transform version is saved separately. This removes trace information, not all source/file-selection clues.

## Validate and freeze

Use validator `faultlens-real-validation-1.1.0`, which copies changed regression assets and test code into both variants. The known Cookiecutter encoding regression supports `--ascii-cookiecutter`: both variants receive the same explicit ASCII locale and retain locale probes. Use a fresh output directory and retain earlier attempts with `--previous-report`.

The freezer requires the corrected validator version and checks asset hashes in both workspaces. Legacy reports must be revalidated. API and worker verify registered source, oracle, and transformed evidence, and block withdrawn snapshots before model calls. Historical results remain readable with a warning; numeric scores and archived research labels are not silently rewritten.

## Run a paired batch

With local services running, from the repository root:

```shell
python scripts/benchmark_real.py --ablation --case-ids ID1,ID2,ID3,ID4,ID5,ID6 --output C:/local/ablation.json --public-summary C:/local/ablation-measurements.json
```

Choose one corrected registry ID per selected case, including excluded controls for the measured selection. IDs appear in the public export. New validation produces different IDs; select those instead of pooling snapshots of one bug.

The runner freezes selection/conditions, alternates full-first/type-only-first order by eligible case, and runs single before chain. It persists uncertain submissions without silent replay. Checks cover strategy pairing, requested modes, changed evidence hashes, shared source/oracle/parent hashes, and runtime consistency. Superseded-validation warnings prevent publication. Full batch files stay private; public exports contain measurements and hashes only.

The comparison tests ranking sensitivity while holding source, oracle, and model settings fixed. It changes diagnostic information and input length together, so it does not isolate target-name leakage or reproduce the historical clean split. Exception types, source, prior model knowledge, and oracle-selected filenames can still guide localization. Small paired results are descriptive.

See the [corrected measured ablation](benchmarks/real-evidence-ablation.md), [real inference](real-inference.md), and [validation methodology](real-case-validation.md).
