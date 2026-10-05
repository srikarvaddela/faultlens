# FaultLens

A reproducible fault-localization workbench. Inspect failing Python tests, compare suspicious-line rankings, and save experiments with their evidence.

## Why build this?

Debugging tools need more than plausible explanations: they need measurable results. FaultLens connects a readable debugging interface with transparent evaluation, making it possible to compare coverage baselines and, in a later milestone, LLM approaches on the same bugs.

## Milestone 1 (in progress)

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

Build history is maintained in small milestone commits. Setup and architecture documentation will accompany the first functional release.
