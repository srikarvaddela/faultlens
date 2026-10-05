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

1. Establish a working, tested baseline and a deployable demo.
2. Add a durable evaluation worker and PostgreSQL deployment.
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

Start both services in one terminal:

```shell
node scripts/dev.mjs
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8000/docs**.

Click **New experiment**, select cases and methods, and run. The application executes the packaged Python tests and saves real results. Explore suspicious lines, inspect expected versus actual values, reveal the known fault, switch baselines, or export an experiment as JSON. Saved runs survive an API restart.

The local default is SQLite for quick setup. To use PostgreSQL, set `DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/faultlens` before starting the backend. Never commit real credentials.

## Run with PostgreSQL using Docker

```shell
docker compose up --build
```

Open **http://127.0.0.1:8080**. This runs React behind Nginx, FastAPI, and PostgreSQL with a persistent volume. The example database credentials are for local development only. Docker is optional; the native setup above is the tested path for this milestone.

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

## What is measured?

- **Ochiai and Tarantula:** established coverage-based ranking formulas.
- **Top-1/Top-3:** known fault within the first one or three positions.
- **MRR:** mean reciprocal rank of the known fault.
- **Conservative ties:** tied lines receive the worst rank of the tied group.
- **Timing:** measured child-process startup, test execution, and ranking, not model latency.

The dataset is six original fixtures with 30 tests. It is small by design and does not support general accuracy claims. Equal baseline results are a valid outcome. Ground truth is excluded from ranking inputs. JSON exports include full precision scores, source and evidence hashes, versions, timestamps, and outcomes.

## Architecture and limitations

See [architecture](docs/architecture.md), [evaluation methodology](docs/methodology.md), and [roadmap](docs/roadmap.md).

This first release is a single-user local workbench. Evaluations run synchronously in the API's thread pool and use short-lived subprocesses with timeouts. There is no durable worker, authentication, arbitrary repository execution, or live LLM inference yet. Subprocesses are **not a security sandbox**. Do not expose this unauthenticated API on a public network.

![FaultLens workbench](docs/screenshots/workbench.png)

## Author

Built by Srikar Vaddela with Codex assistance. This project is independent of prior university research. The implementation, limitations, and milestone commits are documented so the work can be reproduced and discussed.
