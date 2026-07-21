# Reference Runtime

Executable contract test and learning material for SentinelAI.

It implements planner / RAG / verifier / analyzer business logic and consumes
the frozen SDK instrumentation API plus optional SentinelAI Platform
persistence, storage, and HTTP packages. Its composition root configures
SentinelAI once with an in-memory Execution Stream and Platform persistence
subscribers. Business methods use `@execution` / `@span` and return only
business objects. It is not imported by either product.

```bash
uv run uvicorn examples.reference_runtime.main:app --reload
```

## LLM model plugs

Models are selected by name via `OPENROUTER_MODEL_PLUG` (see `.env.example`).
Each plug is a primary OpenRouter model plus optional fallbacks sent with
OpenRouter's `models` array so rate limits / downtime fail over automatically.

| Plug | Primary model | Notes |
| --- | --- | --- |
| `gemma-31b` (default) | `google/gemma-4-31b-it:free` | Strong instruct / JSON |
| `gemma-26b` | `google/gemma-4-26b-a4b-it:free` | Faster MoE |
| `gpt-oss-20b` | `openai/gpt-oss-20b:free` | OpenAI open weights |
| `free-router` | `openrouter/free` | Casual chat only — can pick guardrail models |
| `nemotron-nano` | `nvidia/nemotron-3-nano-30b-a3b:free` | Lighter Nemotron |
| `nemotron-super` | `nvidia/nemotron-3-super-120b-a12b:free` | Stronger Nemotron |
| `nemotron-ultra` | `nvidia/nemotron-3-ultra-550b-a55b:free` | Often rate-limited |
| `laguna-m` | `poolside/laguna-m.1:free` | Coding / agentic |
| `north-code` | `cohere/north-mini-code:free` | Cohere coding MoE |

To add a plug, register a `ModelPlug` in
`examples/reference_runtime/model_plugs.py`. Consumers depend on the
`LLMClient` protocol; the composition root builds the client via
`create_llm_client(settings)`.
