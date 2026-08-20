"""Tests for the Audience section and the node that fills it.

Two things are worth guarding here. The section must be absent, not empty or
hedged, when nothing has been inferred — which is every conversation for its
first few messages, so it is the common case rather than an edge one. And the
node must never be able to fail a translation: it reads a table that may hold
nothing, over a connection that may be gone, for a nicety.

Every test mocks the LLM. Fixtures live in this file rather than
tests/conftest.py, which is shared across all feature areas.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.context_provider import NullContextProvider
from src.agents.customization import Customization, NullCustomizationProvider
from src.agents.graph import build_translation_graph
from src.agents.nodes.translation import make_customize
from src.agents.prompts import build_audience_block

MODULE = "src.agents.nodes.translation"


def make_llm(*responses: str) -> AsyncMock:
    """Fake LLM returning the given contents, one per successive call."""
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(
        side_effect=[type("Msg", (), {"content": r})() for r in responses]
    )
    llm.model_name = "mock-model"
    return llm


class StubProvider:
    """Answers with one fixed customization, or raises."""

    def __init__(self, customization=None, error: Exception | None = None) -> None:
        self.customization = customization or Customization()
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def get_customization(
        self, conversation_id, *, original_text, source_language, target_language
    ) -> Customization:
        self.calls.append((conversation_id, target_language))
        if self.error:
            raise self.error
        return self.customization


def test_an_unprofiled_conversation_gets_no_audience_section():
    """The prompt has to read exactly as it did before the section existed."""
    assert build_audience_block() == ""
    assert build_audience_block(domain="", audience="", honorific_profile="") == ""


def test_the_audience_section_states_the_readers_standing():
    block = build_audience_block(honorific_profile="client")

    assert "# Audience" in block
    assert "client, not a colleague" in block
    # And the guard rail that stops a model inventing courtesies.
    assert "Never add greetings" in block


def test_a_standing_the_prompt_does_not_know_contributes_nothing():
    """A value added to the database ahead of this file must not be able to
    produce a broken prompt, so unknown reads as absent rather than raising."""
    assert build_audience_block(honorific_profile="archbishop") == ""
    # The subject area still comes through on its own.
    assert "software delivery" in build_audience_block(
        domain="software delivery", honorific_profile="archbishop"
    )


@pytest.mark.asyncio
async def test_customize_puts_the_conversation_profile_into_the_state():
    node = make_customize(
        StubProvider(Customization(domain="billing", audience="an external client"))
    )

    result = await node({"conversation_id": "c1", "target_language": "vi"})

    assert result["domain"] == "billing"
    assert result["audience"] == "an external client"
    assert result["telemetry"]["customized"] is True


@pytest.mark.asyncio
async def test_customize_reports_a_conversation_it_learned_nothing_about():
    """`customized` is what will show whether the inference is reaching real
    traffic at all; it has to distinguish "asked and got nothing" from "asked"."""
    node = make_customize(NullCustomizationProvider())

    result = await node({"conversation_id": "c1", "target_language": "vi"})

    assert (result["domain"], result["audience"]) == ("", "")
    assert result["telemetry"]["customized"] is False


@pytest.mark.asyncio
async def test_a_customization_provider_that_raises_does_not_stop_the_translation():
    """Same contract as build_context: a missing audience costs quality, never
    delivery (NFR-02)."""
    node = make_customize(StubProvider(error=RuntimeError("database is gone")))

    result = await node({"conversation_id": "c1", "target_language": "vi"})

    assert (result["domain"], result["audience"]) == ("", "")
    assert result["telemetry"]["customized"] is False


@pytest.mark.asyncio
async def test_customize_asks_nothing_without_a_conversation():
    """The evaluation harness runs states with no conversation behind them."""
    provider = StubProvider(Customization(domain="billing"))
    node = make_customize(provider)

    result = await node({"target_language": "vi"})

    assert provider.calls == []
    assert result["domain"] == ""


@pytest.mark.asyncio
async def test_the_graph_sends_the_readers_standing_to_the_model():
    """End to end through the compiled graph: the standing arrives in the state
    from the fan-out and has to reach the system prompt."""
    llm = make_llm("Kính mong quý khách xem lại")

    with (
        patch(f"{MODULE}._detect_local", return_value="en"),
        patch(f"{MODULE}.get_llm", return_value=llm),
    ):
        graph = build_translation_graph(
            NullContextProvider(),
            customization_provider=StubProvider(
                Customization(domain="software delivery", audience="an external client")
            ),
        )
        await graph.ainvoke(
            {
                "conversation_id": "c1",
                "original_text": "Please review the UI",
                "source_language": "en",
                "target_language": "vi",
                "honorific_profile": "client",
            }
        )

    system_prompt = llm.ainvoke.await_args.args[0][0]["content"]
    assert "# Audience" in system_prompt
    assert "software delivery" in system_prompt
    assert "client, not a colleague" in system_prompt


@pytest.mark.asyncio
async def test_the_graph_omits_the_audience_section_for_an_unprofiled_conversation():
    """The state the fan-out produces before anything has been inferred."""
    llm = make_llm("Xem lại giúp nhé")

    with (
        patch(f"{MODULE}._detect_local", return_value="en"),
        patch(f"{MODULE}.get_llm", return_value=llm),
    ):
        graph = build_translation_graph(NullContextProvider())
        await graph.ainvoke(
            {
                "conversation_id": "c1",
                "original_text": "Please review the UI",
                "source_language": "en",
                "target_language": "vi",
            }
        )

    system_prompt = llm.ainvoke.await_args.args[0][0]["content"]
    assert "# Audience" not in system_prompt
