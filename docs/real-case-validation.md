# Validating real research cases

FaultLens now separates archived claims from fresh reproduction checks. The [measured validation report](benchmarks/real-case-validation.md) covers six preselected BugsInPy cases; all 199 archived capture commit IDs were also checked against pinned benchmark metadata.

The validator reads an existing upstream Git clone without changing it. Each test runs in a new workspace directory made from `git archive` at the pinned buggy or fixed commit. Both variants receive identical regression test files from the fixed revision, following BugsInPy's test transplant convention. It never runs scripts from the research archive, `setup.sh`, or tox setup.

## Reproduction and source gates

- The local clone origin must match the benchmark project URL and both revisions must be full commit hashes.
- Every old patch context must match the buggy source. Applying the benchmark patch must also produce the complete corresponding fixed file.
- Removed old-file lines and purely additive insertion anchors remain distinct. AST mapping identifies the innermost containing function; module and class-body changes remain such.
- A Python import-origin probe checks that source modules resolve to the fresh workspace files, rather than an editable installation pointing at an old research checkout.
- The buggy regression test must fail, and the identical test must pass on the fixed version. Import errors, zero tests, timeouts, and failures on both versions do not pass this gate.
- Python versions, installed package inventories, commands, test-file hashes, raw outputs, output hashes, adjustments, and prior attempt summaries are retained locally.

Fresh reproduction is necessary input validation. It does not certify historical prompt identity, establish semantic accuracy of archived answers, or show that evidence lacks fault-location clues. Inputs can now be frozen separately for [file-conditioned real-case inference](real-inference.md). The Research readiness panel itself does not launch model calls.

## Run locally

On Windows with Ubuntu WSL and existing project-specific Python environments, run from `backend`:

```powershell
.venv\Scripts\python -m app.validate_real_cases `
  --benchmark C:/local/BugsInPy `
  --repos C:/local/upstream-clones `
  --captures C:/local/research/code/real_errors `
  --environments /home/user/miniconda3/envs `
  --output C:/local/validation-new `
  --import-id YOUR_LOCAL_RESEARCH_IMPORT_ID `
  --public-summary C:/local/validation-summary.json
```

The benchmark path must contain `projects/`; clone folders must be named `black_repo`, `httpie_repo`, `fastapi_repo`, and `cookiecutter_repo`. Python environments must be named `bug_black`, etc. Obtain upstream revisions referenced by `bug.info`. Pin the BugsInPy clone to the report's benchmark revision before reproducing that audit. The output directory must be new; prior source directories are never reset. Use repeated `--previous-report PATH/validation.json` arguments to retain earlier setup attempts.

`--import-id` attaches the ledger to the existing local study. Reopen **Research** to see **Real-case readiness**, with expandable source locations and fresh outputs. The optional public export uses an allowlist and omits raw traces, machine paths, commands, and package inventories. Raw validation outputs belong outside the public repository.

## Environment and scope

The runner reuses explicitly selected existing WSL environments. It does not install or change their dependencies. Python patch versions and package versions can differ from the original benchmark; recorded inventories make these differences inspectable. Tests are bounded to 90 seconds and run as local subprocesses, **not a security sandbox**.

For the measured batch, Black required an inert generated version constant and an empty test package marker. Documentation symlinks were omitted. Explicit pytest regression tests clear configured `addopts`, which removes an unavailable coverage-plugin requirement. Cookiecutter's archived tox recipe is translated to an explicit pytest target; this checks the regression but does not reproduce tox's original environment setup. All adjustments apply consistently to buggy and fixed variants and are listed in the ledger.

The validator records upstream license artifact paths, hashes, and pinned URLs. It publishes metadata, not copies of upstream source or private research captures. BugsInPy itself is referenced as an external benchmark; this milestone does not redistribute its dataset.
