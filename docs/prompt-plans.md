# Frozen prompt plans

Prompt lab prepares versioned, provider-neutral inputs for curated fixtures without calling a model. It executes the trusted fixture tests locally, freezes selected evidence and numbered buggy source, stores the exact first-step messages, and records their SHA-256 hashes. Preparing a plan creates no experiment outcome, model usage, or billing.

The new `faultlens-prompts-1.0.0` templates support a direct single prompt, a three-step chain where raw evidence appears only at the first step, and a chain that directly restates evidence at later steps. Earlier model analyses may still repeat evidence in either chain. These templates follow the study's general structure but do not reproduce its exact prompts.

Evidence can contain full failing-test outcomes or only captured exception messages. Wrong-output failures can have no exception, which remains explicit rather than being filled with fabricated text. Ground-truth labels and corrected source are excluded. Buggy source and failure details can still expose clues; neither mode is certified leakage-free.

Only the first step is materialized during preparation. A pure renderer constructs later messages from the frozen plan and actual prior responses. Live execution must save every rendered message before making its provider call, then retain the returned response, model/version/configuration, token usage, timing, and request identifiers. A prepared plan by itself does not prove what a model saw.

A strict future-response parser requires one to three distinct, valid source line numbers and nonempty reasons in a JSON candidates array. It records parse errors instead of accepting invalid outputs; it does not score accuracy. Local Ollama execution now persists each materialized request and response, with bounded generation and explicit retries. Remote providers and billing budgets remain future work. See [Ollama integration](ollama.md).

Plans are saved in the local database and can be reopened or exported as JSON. Old plans retain their original templates and messages when code changes.
