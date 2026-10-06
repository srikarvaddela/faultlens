# Local Ollama comparisons

Run Ollama on the same host as the native FaultLens backend and install a local model. The native endpoint defaults to `http://127.0.0.1:11434`; `OLLAMA_BASE_URL` may select another HTTP loopback port. External hosts, credential URLs, redirects, cloud aliases, and remote-model tags are not supported. This integration is currently for the native setup, not the Docker deployment.

```shell
ollama serve
ollama pull llama3.2:1b
```

In Prompt lab, prepare a plan, select an installed model, and choose **Compare single vs evidence-carrying chain** or **Run selected plan only**. A comparison uses one curated bug and identical frozen source/evidence in both methods. It makes four calls: one direct localization and three chain steps. It is a smoke test, not a benchmark or a reproduction of the archived GPT-5 study.

## Retained evidence

Every complete request body and its messages are saved before sending. Subsequent steps incorporate the actual prior responses. Saved transcripts retain full Ollama responses, model digest, server version, options, prompt/evidence hashes, wall-clock latency, token counts and native timing fields where returned, and final parse/line-ranking results. Exports preserve partial calls even on failure. Ground truth enters grading only; it is not included in model request bodies.

Default options are temperature 0, seed 42, 256 generated tokens per call, and a 4096-token context. Final calls request a JSON candidates schema, then use the strict parser. A malformed or missing final response is surfaced as a parse failure, not silently repaired. Fixed settings do not guarantee deterministic inference across machines or runtimes. Calls execute sequentially; cold model loading and cache reuse affect wall time, so these timings are not a fair comparative latency benchmark. Native load_duration is preserved and shown when returned. A length stop is also retained so truncated intermediate analyses remain visible.

## Jobs and failures

Inference uses the persistent job queue. A lease-renewal thread maintains ownership during a model call. Cancellation is cooperative between calls and may wait for the current HTTP call's 180-second timeout. No automatic inference retries occur after provider errors or worker recovery; an interrupted call may have completed at Ollama without its response being captured. Explicit Retry starts a new run with fresh call history. Missing or changed model identities fail the run rather than silently substituting a model.

There are no external provider API charges for this local integration; resource consumption is not tracked as a dollar cost. The Ollama server and local database are unauthenticated development services and must remain bound locally. Imported research stays separate from these new curated-case results.

API contract references: [chat](https://docs.ollama.com/api/chat), [model inventory](https://docs.ollama.com/api/tags), and [structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
