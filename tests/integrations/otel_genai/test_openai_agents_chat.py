"""VCR integration tests: OpenAI Agents SDK -> OTel spans -> chat view.

These tests run real OpenAI Agents SDK code with VCR-replayed HTTP
responses, collect OTel spans via InMemorySpanExporter, run them through
the full extraction + normalization pipeline, and assert the resulting
chat view is correct.

Uses ``weave.otel.instrumentors.openai_agents.instrument()`` — the Weave-
native instrumentor that replaces the community
``opentelemetry-instrumentation-openai-agents-v2`` package.

To record cassettes:
    OPENAI_API_KEY=sk-... pytest tests/integrations/otel_genai/test_openai_agents_chat.py --vcr-record=all
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from agents import Agent, Runner, function_tool

from tests.integrations.otel_genai.conftest import otel_spans_to_genai_schemas
from weave.otel.instrumentors.openai_agents import instrument, uninstrument
from weave.trace_server.genai_chat_view import build_chat_messages


@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    forecasts = {
        "san francisco": "Foggy, 58°F, wind 12 mph W",
        "tokyo": "Clear, 75°F, humidity 45%",
        "london": "Rainy, 52°F, wind 8 mph SW",
        "barcelona": "Sunny, 82°F, UV index 7",
    }
    return forecasts.get(city.lower(), f"Partly cloudy, 68°F in {city}")


@function_tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for available flights."""
    return f"Found 2 flights from {origin} to {destination} on {date}: UA 234 $389, DL 567 $425"


@pytest.fixture(autouse=True)
def _instrument_openai_agents(otel_setup: tuple) -> Generator[None, None, None]:
    """Instrument the OpenAI Agents SDK using the Weave instrumentor."""
    provider, _ = otel_setup
    proc = instrument(
        provider,
        capture_media=False,
        capture_reasoning=False,
        capture_compaction=False,
    )
    yield
    uninstrument(proc)


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "openai-organization"],
    allowed_hosts=["localhost"],
)
@pytest.mark.asyncio
async def test_single_turn_with_tool(otel_setup):
    """Single turn: user asks weather, agent calls tool, responds."""
    provider, exporter = otel_setup

    agent = Agent(
        name="WeatherBot",
        instructions="You are a weather specialist. Use get_weather to look up weather.",
        tools=[get_weather],
        model="gpt-4o-mini",
    )
    result = await Runner.run(agent, "What's the weather in Tokyo?")
    assert result.final_output is not None

    provider.force_flush()
    schemas = otel_spans_to_genai_schemas(exporter)
    assert len(schemas) > 0

    msgs = build_chat_messages(schemas)
    types = [m.type for m in msgs]

    assert "user_message" in types, "Should have a user message"
    assert "agent_start" in types, "Should have an agent_start for WeatherBot"
    assert "tool_call" in types, "Should have at least one tool call"
    assert "agent_message" in types, "Should have an agent response"

    user_msg = next(m for m in msgs if m.type == "user_message")
    assert "tokyo" in user_msg.text.lower() or "weather" in user_msg.text.lower()

    tool_msg = next(m for m in msgs if m.type == "tool_call")
    assert tool_msg.tool_name == "get_weather"

    agent_msg = next(m for m in msgs if m.type == "agent_message")
    assert len(agent_msg.text) > 0


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "openai-organization"],
    allowed_hosts=["localhost"],
)
@pytest.mark.asyncio
async def test_handoff_to_subagent(otel_setup):
    """Triage agent hands off to a specialist subagent."""
    provider, exporter = otel_setup

    weather_agent = Agent(
        name="WeatherBot",
        instructions="Use get_weather tool.",
        tools=[get_weather],
        model="gpt-4o-mini",
        handoff_description="Weather specialist",
    )
    triage_agent = Agent(
        name="TriageAgent",
        instructions="Route to WeatherBot for weather questions. Always hand off.",
        handoffs=[weather_agent],
        model="gpt-4o-mini",
    )
    result = await Runner.run(triage_agent, "What's the weather in Barcelona?")
    assert result.final_output is not None

    provider.force_flush()
    schemas = otel_spans_to_genai_schemas(exporter)
    msgs = build_chat_messages(schemas)
    types = [m.type for m in msgs]

    assert "user_message" in types
    agent_starts = [m for m in msgs if m.type == "agent_start"]
    agent_names = {m.agent_name for m in agent_starts}
    assert "TriageAgent" in agent_names, "Should show TriageAgent start"
    assert "WeatherBot" in agent_names, "Should show WeatherBot start after handoff"

    assert any(m.type in {"agent_handoff"} for m in msgs), "Should have a handoff message"

    assert "agent_message" in types, "Should have a final agent response"


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "openai-organization"],
    allowed_hosts=["localhost"],
)
@pytest.mark.asyncio
async def test_multi_turn_context_preserved(otel_setup):
    """Multi-turn: second turn only shows its own user prompt, not full history."""
    provider, exporter = otel_setup

    agent = Agent(
        name="WeatherBot",
        instructions="Use get_weather for weather questions. Be brief.",
        tools=[get_weather],
        model="gpt-4o-mini",
    )

    from agents import SQLiteSession

    session = SQLiteSession("test-session")

    result1 = await Runner.run(agent, "What's the weather in Tokyo?", session=session)
    assert result1.final_output is not None

    provider.force_flush()
    exporter.clear()

    result2 = await Runner.run(agent, "How about London?", session=session)
    assert result2.final_output is not None

    provider.force_flush()
    schemas = otel_spans_to_genai_schemas(exporter)
    msgs = build_chat_messages(schemas)

    user_msgs = [m for m in msgs if m.type == "user_message"]
    assert len(user_msgs) == 1, "Should have exactly one user message for this turn"
    assert "london" in user_msgs[0].text.lower(), \
        f"User message should be about London, got: {user_msgs[0].text}"
    assert "tokyo" not in user_msgs[0].text.lower(), \
        "Should NOT include previous turn's question"
