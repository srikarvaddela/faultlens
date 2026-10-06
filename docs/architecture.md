# Architecture

```mermaid
flowchart LR
    UI[React + TypeScript] -->|same-origin /api| API[FastAPI]
    API --> DB[(SQLite local / PostgreSQL optional)]
    API --> Queue[(Durable job queue)]
    Queue --> Worker[Leased worker]
    Worker --> Eval[Evaluation service]
    Eval --> Runner[Trusted fixture subprocess]
    Runner --> Evidence[Per-test coverage + outcomes]
    Evidence --> Rank[Ochiai / Tarantula]
    Rank --> Score[Ground-truth scoring]
    Score --> DB
    Worker --> LocalModel[Local Ollama]
    LocalModel --> Transcript[Saved requests and responses]
    Transcript --> DB
    Freeze[Offline validated-input freezer] --> RealRegistry[(Local real-case registry)]
    RealRegistry --> API
```

## Request flow

1. The browser fetches the catalog and experiment history.
2. A validated run request selects packaged bug IDs and ranking methods and persists a queued job.
3. A separate worker claims the job with a lease. For each bug, it launches Python with `-I` and a ten-second timeout, passing source and tests through stdin. Ground truth and corrected source are absent from that input.
4. The runner collects executed line numbers with Python tracing. Numeric results use a small comparison tolerance; other values use equality.
5. Both methods reuse the same coverage to produce suspiciousness scores. Scoring then looks up the known fault.
6. A complete experiment and completed job state are published atomically. Failure, cancellation, or a lost lease does not publish partial results.
7. The browser displays the returned measured evidence and can export the full record.

## Decisions

- **SQLite locally, SQLAlchemy for both database engines:** quick setup without blocking the PostgreSQL path.
- **Database-backed worker:** survives API restarts without a separate broker. Conditional claims and lease tokens fence stale workers. See [queue semantics](queue.md).
- **Original fixtures:** clean provenance and reproducible failure/fix pairs before importing real-world projects.
- **Two spectrum baselines before LLMs:** verify measurement integrity before introducing prompt, inference, and leakage variables.
- **No arbitrary code execution:** the runner is limited to the trusted packaged catalog. A subprocess timeout is not a sandbox.
- **Single origin:** Vite proxies API requests locally; Nginx does the same in Docker, avoiding broad CORS rules.

## Limits

No authentication, migration framework, or pagination beyond the latest 100 records yet. Shared hosting requires authentication, rate limits, explicit resource bounds, and migrations. The Docker/PostgreSQL path is provided but is not validated until a Docker runtime is available. The native SQLite path and browser workflow are tested.
