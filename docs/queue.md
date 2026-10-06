# Durable evaluation jobs

`POST /api/jobs` validates a request, saves it, and returns HTTP 202 immediately. `python -m app.worker` runs separately; `scripts/dev.mjs` starts it alongside the API and frontend.

Jobs move through queued, running, completed, failed, and cancelled states. Conditional database updates and unique lease tokens prevent concurrent ownership. Leases last 60 seconds and are renewed between cases; each fixture subprocess has a ten-second timeout. Expired jobs can be reclaimed. Stale workers cannot renew or publish into a newer claim. Failed execution and expired leases consume at most three attempts.

Completed job state and experiment publication share one transaction. Evaluation can execute more than once after a crash, but a successful job publishes one experiment with its job ID. Partial evidence is not persisted; retries restart the whole evaluation. Both methods share evidence collected once per bug.

Cancellation is cooperative: queued jobs cancel immediately; running jobs stop between bounded fixture processes. Completed jobs cannot be cancelled. Explicit Retry creates a new job and budget, preserving the original audit history.

Endpoints: `POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`, and `POST /api/jobs/{id}/retry`. The UI polls progress, restores active work after reload, and opens completed results. The deprecated synchronous experiment endpoint remains for compatibility.

SQLite is tested locally. PostgreSQL deployment remains unverified. API and worker serialize additive schema setup; full migrations are still planned. Authentication, queue admission limits, scheduled backoff, and durable partial checkpoints remain future work. Only trusted packaged fixtures execute.
