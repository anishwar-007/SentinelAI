"""Named OpenRouter model plugs for the reference runtime.

Swap models by setting ``OPENROUTER_MODEL_PLUG=<name>`` (or overriding
``OPENROUTER_MODEL`` / ``OPENROUTER_MODEL_FALLBACKS``). Each plug carries a
primary OpenRouter model id plus optional fallbacks passed via OpenRouter's
``models`` array so rate limits / downtime fail over automatically.

Fallbacks are chat/instruct models only. Do not put ``openrouter/free`` in a
structured-JSON fallback chain — the free router can select guardrail models
(e.g. Nemotron Content Safety) that return ``User Safety: safe`` instead of JSON.
"""

from __future__ import annotations

from dataclasses import dataclass

# Chat / instruct free models suitable for planner JSON + general completion.
_STRUCTURED_FALLBACKS: tuple[str, ...] = (
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
)


@dataclass(frozen=True, slots=True)
class ModelPlug:
    """A drop-in LLM selection for the reference runtime."""

    name: str
    model: str
    fallbacks: tuple[str, ...] = ()
    description: str = ""
    provider: str = "openrouter"

    @property
    def routing_models(self) -> tuple[str, ...]:
        """Primary model followed by unique fallbacks (OpenRouter order)."""
        seen: set[str] = {self.model}
        ordered = [self.model]
        for fallback in self.fallbacks:
            if fallback not in seen:
                seen.add(fallback)
                ordered.append(fallback)
        return tuple(ordered)


def _fallbacks_excluding(*exclude: str) -> tuple[str, ...]:
    blocked = {item for item in exclude}
    return tuple(model for model in _STRUCTURED_FALLBACKS if model not in blocked)


MODEL_PLUGS: dict[str, ModelPlug] = {
    "free-router": ModelPlug(
        name="free-router",
        model="openrouter/free",
        description=(
            "OpenRouter free-model router (random free model). Useful for "
            "casual chat only — not for planner/verifier JSON; may pick "
            "guardrail or multimodal models."
        ),
    ),
    "gemma-31b": ModelPlug(
        name="gemma-31b",
        model="google/gemma-4-31b-it:free",
        fallbacks=_fallbacks_excluding("google/gemma-4-31b-it:free"),
        description=(
            "Gemma 4 31B instruct — strong instruction following and JSON."
        ),
    ),
    "gemma-26b": ModelPlug(
        name="gemma-26b",
        model="google/gemma-4-26b-a4b-it:free",
        fallbacks=_fallbacks_excluding("google/gemma-4-26b-a4b-it:free"),
        description=(
            "Gemma 4 26B MoE (fast / efficient). Good general chat + planning."
        ),
    ),
    "gpt-oss-20b": ModelPlug(
        name="gpt-oss-20b",
        model="openai/gpt-oss-20b:free",
        fallbacks=_fallbacks_excluding("openai/gpt-oss-20b:free"),
        description="OpenAI gpt-oss-20b (Apache 2.0) — solid structured output.",
    ),
    "nemotron-nano": ModelPlug(
        name="nemotron-nano",
        model="nvidia/nemotron-3-nano-30b-a3b:free",
        fallbacks=_fallbacks_excluding("nvidia/nemotron-3-nano-30b-a3b:free"),
        description=(
            "Nemotron 3 Nano 30B — lighter agentic model; usually less "
            "contended than Ultra."
        ),
    ),
    "nemotron-super": ModelPlug(
        name="nemotron-super",
        model="nvidia/nemotron-3-super-120b-a12b:free",
        fallbacks=_fallbacks_excluding(),
        description="Nemotron 3 Super 120B — stronger multi-agent / reasoning.",
    ),
    "nemotron-ultra": ModelPlug(
        name="nemotron-ultra",
        model="nvidia/nemotron-3-ultra-550b-a55b:free",
        fallbacks=(
            "nvidia/nemotron-3-super-120b-a12b:free",
            *_fallbacks_excluding(),
        ),
        description=(
            "Nemotron 3 Ultra 550B — highest capacity; often rate-limited on free."
        ),
    ),
    "laguna-m": ModelPlug(
        name="laguna-m",
        model="poolside/laguna-m.1:free",
        fallbacks=(
            "cohere/north-mini-code:free",
            *_fallbacks_excluding(),
        ),
        description="Poolside Laguna M.1 — coding / agentic tool-use oriented.",
    ),
    "north-code": ModelPlug(
        name="north-code",
        model="cohere/north-mini-code:free",
        fallbacks=(
            "poolside/laguna-m.1:free",
            *_fallbacks_excluding(),
        ),
        description="Cohere North Mini Code — agentic coding MoE.",
    ),
}

DEFAULT_MODEL_PLUG: str = "gemma-31b"


def get_model_plug(name: str) -> ModelPlug:
    key = name.strip().lower()
    try:
        return MODEL_PLUGS[key]
    except KeyError as exc:
        available = ", ".join(sorted(MODEL_PLUGS))
        raise ValueError(
            f"Unknown model plug {name!r}. Available plugs: {available}"
        ) from exc


def list_model_plugs() -> list[ModelPlug]:
    return [MODEL_PLUGS[name] for name in sorted(MODEL_PLUGS)]


def resolve_model_plug(
    *,
    plug_name: str | None = None,
    model_override: str | None = None,
    fallbacks_override: tuple[str, ...] | None = None,
) -> ModelPlug:
    """Resolve the active plug from env-style overrides.

    - ``plug_name`` selects a named registry entry (default: gemma-31b).
    - ``model_override`` replaces the plug's primary OpenRouter model id.
    - ``fallbacks_override`` replaces the plug's fallback chain.
    """
    base = get_model_plug(plug_name or DEFAULT_MODEL_PLUG)
    model = (model_override or "").strip() or base.model
    if fallbacks_override is not None:
        fallbacks = fallbacks_override
    else:
        fallbacks = base.fallbacks
    if model == base.model and fallbacks == base.fallbacks:
        return base
    return ModelPlug(
        name=base.name,
        model=model,
        fallbacks=fallbacks,
        description=base.description,
        provider=base.provider,
    )
