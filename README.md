# FaultLens

A reproducible fault-localization workbench. Inspect failing Python tests, compare suspicious-line rankings, and save experiments with their evidence.

## Why build this?

Debugging tools need more than plausible explanations: they need measurable results. FaultLens connects a readable debugging interface with transparent evaluation, making it possible to compare coverage baselines and, in a later milestone, LLM approaches on the same bugs.

## Milestone 1

- React + TypeScript debugging workbench
- FastAPI experiment API and SQLAlchemy persistence
- Original, curated Python bugs with executable tests
- Ochiai and Tarantula spectrum-based fault-localization baselines
- Reproducible results, conservative tie handling, and saved comparisons

This is an educational project, independent of BugsInPy and previous university research. Its small curated dataset is not evidence of real-world model performance. Live LLM execution and arbitrary repository ingestion are planned, not implemented.

## Planned next

1. Validate PostgreSQL deployment and add schema migrations.
2. Add authenticated experiment ownership and worker observability.
3. Integrate live LLM methods with versioned prompts, usage tracking, and leakage-controlled evidence.
4. Import a documented real-world benchmark and report paired comparisons.

## Run locally

Requires **Python 3.12+** and **Node.js 24+**. No API key is required.

From the repository root, create the backend environment:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
cd ../frontend
npm ci
cd ..
```

On macOS/Linux, use `python3` and `.venv/bin/python` in place of the Windows commands.

Start the API, durable worker, and frontend in one terminal:

```shell
node scripts/dev.mjs
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8000/docs**.

Click **New experiment**, select cases and methods, and run. The API queues a persistent job; the worker executes tests and publishes complete results. Job progress, cancellation, and retries are visible in the interface. Explore suspicious lines, inspect expected versus actual values, reveal the known fault, switch baselines, or export an experiment as JSON. Queued jobs and saved runs survive an API restart. If a worker stops mid-run, another worker reclaims the job after its 60-second lease expires. Automatic retries are bounded to three attempts; explicit Retry creates a new job.

The local default is SQLite for quick setup. To use PostgreSQL, set `DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/faultlens` before starting the backend. Never commit real credentials.

## Run with PostgreSQL using Docker

```shell
docker compose up --build
```

Open **http://127.0.0.1:8080**. This runs React behind Nginx, FastAPI, a separate worker, and PostgreSQL with a persistent volume. The example database credentials are for local development only. Docker is optional; the native setup above is the tested path for this milestone.

## Validate

```powershell
cd backend
.venv\Scripts\python -m pytest -q
cd ../frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests launch their own services on ports 8010 and 5174. They exercise real evaluations, evidence inspection, exports, persistence, selection validation, mobile layout, and methodology. API/evaluator tests cover fixture reproduction, fixed-code validation, mathematical scoring, tie handling, exclusion of ground truth, invalid input, and runner timeouts. GitHub Actions runs backend tests on Windows and Linux plus frontend build and Chromium workflows.

## Inspect archived research

From `backend`, run `python -m app.import_research /path/to/study.zip --name "Research archive"`, then open **Research** in the UI. The offline adapter reads recorded CSV outcomes, preserves unknown leakage labels, and keeps repeated runs separate. Where saved final answers exist, use the answer audit to inspect responses beside ground truth and review possible scoring artifacts without changing recorded results. A separate capture-derived view shows function-name matches with inspectable traces and provenance; it does not reproduce the original historical leakage split. Your imported data stays in the ignored local database; archive scripts never execute and no model calls are made. See [research import methodology](docs/research-import.md).

The Research view also supports [fresh real-case validation](docs/real-case-validation.md): pinned source and patch checks, import-origin verification, and paired buggy/fixed regression tests with local logs. The [measured six-case audit](docs/benchmarks/real-case-validation.md) has five cases ready for prompt review and one excluded control. Freeze eligible inputs to run [file-conditioned real-case inference](docs/real-inference.md); the [first measured comparison](docs/benchmarks/real-ollama-comparison.md) covers three cases with full files and records all exclusions.

## Prepare reproducible prompt inputs

The [corrected evidence ablation](docs/benchmarks/real-evidence-ablation.md) compares full traces with exception-type-only evidence on three real cases. It also corrects a missing-fixture confound in the earlier Cookiecutter run; prior reports are marked superseded. [Workflow and guards](docs/evidence-ablation.md) retain matched assets, evidence lineage, exclusions, and historical warnings.

Open **Prompt lab** to prepare a single-prompt or three-step plan from a curated case. Preparing plans preserves evidence, prompt versions, exact first-step messages, and hashes without making model calls. You can then run a local Ollama comparison and inspect every saved call and response. Later messages require actual prior responses. See [prompt-plan methodology](docs/prompt-plans.md) and [local Ollama setup](docs/ollama.md).

## Local model benchmark

The checkpointed runner compares single prompts with evidence-carrying three-step chains on all six curated bugs. It retains failed trials, exact call transcripts, native usage, truncation, and load timing. See the [measured llama3.2:1b report](docs/benchmarks/llama3.2-1b-curated.md) and its JSON export. With the native API, worker, and Ollama running, reproduce from the repository root:

```shell
python scripts/benchmark_ollama.py --model llama3.2:1b --repeats 3 --output benchmark-local.json
```

An existing output resumes known runs; choose a new path for a fresh batch. Fixed-seed repeats check repeatability and do not enlarge the six-bug sample.

## Workbench metrics

- **Ochiai and Tarantula:** established coverage-based ranking formulas.
- **Top-1/Top-3:** known fault within the first one or three positions.
- **MRR:** mean reciprocal rank of the known fault.
- **Conservative ties:** tied lines receive the worst rank of the tied group.
- **Timing:** shared evidence collection plus per-method ranking, not model latency. Exports retain both timing components.

The dataset is six original fixtures with 30 tests. It is small by design and does not support general accuracy claims. Equal baseline results are a valid outcome. Ground truth is excluded from ranking inputs. JSON exports include full precision scores, source and evidence hashes, versions, timestamps, and outcomes.

## Architecture and limitations

See [architecture](docs/architecture.md), [evaluation methodology](docs/methodology.md), and [roadmap](docs/roadmap.md).

This release is a single-user local workbench with a database-backed queue and a separate worker. Only complete experiments are published; cancellation is cooperative between cases. Each trusted fixture subprocess has a ten-second timeout. Live local inference is available through Ollama; there is no authentication or arbitrary repository execution yet. The deprecated synchronous experiment endpoint remains for compatibility; the UI uses the queue. Subprocesses are **not a security sandbox**. Do not expose this unauthenticated API on a public network.

![FaultLens workbench](docs/screenshots/workbench.png)
