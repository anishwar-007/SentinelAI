# Reference Runtime

Executable contract test and learning material for SentinelAI.

It implements planner / RAG / verifier / analyzer business logic and consumes
the SDK public API plus optional SentinelAI Platform persistence, storage, and
HTTP packages. Its composition root configures SentinelAI once with an
in-memory Execution Stream and Platform persistence subscribers. Business
methods use `@observe_execution` / `@observe(capture=...)` and do not manage
SDK lifecycle manually. It is not imported by either product.

```bash
uv run uvicorn examples.reference_runtime.main:app --reload
```
