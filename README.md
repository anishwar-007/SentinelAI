# AI Observability Platform — Milestone 1

A minimal command-line app that sends a prompt to an LLM through
[OpenRouter](https://openrouter.ai) and prints the response.

This is the foundation. Later milestones add tracing, evaluation, and more.
For now the goal is deliberately small: **prompt in, response out.**

## Project structure

```
app/
  __init__.py    # marks app/ as a Python package
  config.py      # loads & validates settings (API key, model)
  schemas.py     # Pydantic models: ChatMessage, LLMResponse
  llm.py         # OpenRouterClient: the only code that talks HTTP
  main.py        # CLI entry point: wires it all together
.env.example     # template for your secrets (copy to .env)
pyproject.toml   # project metadata & dependencies (used by uv)
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

## 1. Install dependencies

`uv` reads `pyproject.toml`, creates a virtual environment, and installs
everything in one step:

```bash
uv sync
```

## 2. Get an OpenRouter API key

1. Sign up at https://openrouter.ai
2. Go to https://openrouter.ai/keys
3. Create a new key and copy it.

The default model is `google/gemma-3-4b-it:free`, which is free to use.

## 3. Create your .env file

Copy the template and paste your key in:

```bash
cp .env.example .env
```

Then edit `.env`:

```
OPENROUTER_API_KEY=sk-or-your-real-key-here
```

> The `.env` file is git-ignored. Never commit your real key.

## 4. Run it

```bash
uv run python -m app.main
```

You'll be prompted:

```
Enter Prompt: Explain what an API key is in one sentence.
========================
MODEL    : google/gemma-3-4b-it:free
RESPONSE : An API key is a secret token that identifies and authorizes...
TOKENS   : {'prompt_tokens': 14, 'completion_tokens': 28, 'total_tokens': 42}
========================
```

## How it fits together

```
main.py  ──uses──▶  config.load_settings()   (get validated API key + model)
   │
   └──uses──▶  OpenRouterClient.generate()    (build request, call API, parse)
                        │
                        └──returns──▶  LLMResponse  (model, response, usage)
```

Dependencies point *inward*: `main` depends on `llm`, `llm` depends on
`schemas`. Nothing depends on `main`. Swapping providers later means editing
only `llm.py`.
