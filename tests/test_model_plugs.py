from __future__ import annotations

import pytest

from examples.reference_runtime.model_plugs import (
    DEFAULT_MODEL_PLUG,
    get_model_plug,
    list_model_plugs,
    resolve_model_plug,
)


def test_default_plug_is_registered() -> None:
    plug = get_model_plug(DEFAULT_MODEL_PLUG)
    assert plug.model
    assert plug.provider == "openrouter"


def test_list_model_plugs_covers_openrouter_options() -> None:
    names = {plug.name for plug in list_model_plugs()}
    assert {
        "free-router",
        "gemma-31b",
        "gpt-oss-20b",
        "nemotron-nano",
        "nemotron-ultra",
    } <= names


def test_resolve_model_plug_overrides() -> None:
    plug = resolve_model_plug(
        plug_name="gemma-31b",
        model_override="openai/gpt-oss-20b:free",
        fallbacks_override=("openrouter/free",),
    )
    assert plug.name == "gemma-31b"
    assert plug.model == "openai/gpt-oss-20b:free"
    assert plug.fallbacks == ("openrouter/free",)
    assert plug.routing_models == (
        "openai/gpt-oss-20b:free",
        "openrouter/free",
    )


def test_structured_plugs_do_not_fallback_to_free_router() -> None:
    for plug in list_model_plugs():
        if plug.name == "free-router":
            continue
        assert "openrouter/free" not in plug.fallbacks
        assert "content-safety" not in plug.model


def test_unknown_plug_raises() -> None:
    with pytest.raises(ValueError, match="Unknown model plug"):
        get_model_plug("not-a-real-plug")
