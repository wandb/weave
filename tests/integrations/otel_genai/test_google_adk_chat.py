"""VCR integration tests: Google ADK -> OTel spans -> chat view.

These tests run real Google ADK code with VCR-replayed HTTP responses,
collect OTel spans via the ADK's built-in OTel tracing, run them through
the full extraction + normalization pipeline, and assert the resulting
chat view is correct.

Uses ``weave.otel.instrumentors.google_adk.instrument()`` to enrich
ADK's native spans with system instructions, tool definitions, and
conversation tracking.

To record cassettes:
    GOOGLE_API_KEY=... pytest tests/integrations/otel_genai/test_google_adk_chat.py --vcr-record=all
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from tests.integrations.otel_genai.conftest import otel_spans_to_genai_schemas
from weave.agents.instrumentors.google_adk import instrument, uninstrument
from weave.trace_server.genai_chat_view import build_chat_messages


def _get_weather(city: str) -> str:
    """Get the current weather for a city."""
    forecasts = {
        "san francisco": "Foggy, 58°F, wind 12 mph W",
        "tokyo": "Clear, 75°F, humidity 45%",
        "london": "Rainy, 52°F, wind 8 mph SW",
        "paris": "Overcast, 61°F, light drizzle",
    }
    return forecasts.get(city.lower(), f"Partly cloudy, 68°F in {city}")


def _calculator(expression: str) -> str:
    """Evaluate an arithmetic expression."""
    allowed = set("0123456789+-*/.(). ")
    if not all(c in allowed for c in expression):
        return f"Error: invalid characters in expression: {expression}"
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["localhost"],
)
@pytest.mark.asyncio
async def test_single_turn_with_tool(otel_setup):
    """Single turn: user asks weather, agent delegates to WeatherAgent."""
    provider, exporter = otel_setup

    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    weather_agent = LlmAgent(
        name="WeatherAgent",
        model="gemini-2.0-flash",
        description="Weather specialist",
        instruction="Use get_weather tool.",
        tools=[_get_weather],
    )
    coordinator = LlmAgent(
        name="Coordinator",
        model="gemini-2.0-flash",
        description="Routes to specialists.",
        instruction="Delegate to WeatherAgent for weather. Always delegate.",
        sub_agents=[weather_agent],
    )

    proc = instrument(provider, agents=[coordinator], capture_media=False)

    try:
        runner = InMemoryRunner(agent=coordinator, app_name="test_app")
        session = await runner.session_service.create_session(
            app_name="test_app", user_id="user1"
        )

        user_msg = types.Content(
            role="user", parts=[types.Part(text="What's the weather in Tokyo?")]
        )

        final_text = ""
        async for event in runner.run_async(
            user_id="user1", session_id=session.id, new_message=user_msg
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_text = part.text

        assert final_text, "Agent should produce a response"

        provider.force_flush()
        schemas = otel_spans_to_genai_schemas(exporter)
        assert len(schemas) > 0, "Should have collected OTel spans"

        msgs = build_chat_messages(schemas)
        types_found = [m.type for m in msgs]

        assert "user_message" in types_found, "Should have a user message"
        assert any(t in {"agent_message"} for t in types_found), "Should have an agent response"
    finally:
        uninstrument(proc)


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["localhost"],
)
@pytest.mark.asyncio
async def test_multi_turn_session(otel_setup):
    """Multi-turn: two queries in same session, second turn uses last-only prompt."""
    provider, exporter = otel_setup

    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = LlmAgent(
        name="WeatherAgent",
        model="gemini-2.0-flash",
        description="Weather specialist",
        instruction="Use get_weather for weather. Be brief.",
        tools=[_get_weather],
    )

    proc = instrument(provider, agents=[agent], capture_media=False)

    try:
        runner = InMemoryRunner(agent=agent, app_name="test_app")
        session = await runner.session_service.create_session(
            app_name="test_app", user_id="user1"
        )

        msg1 = types.Content(
            role="user", parts=[types.Part(text="Weather in Tokyo?")]
        )
        async for _event in runner.run_async(
            user_id="user1", session_id=session.id, new_message=msg1
        ):
            pass

        provider.force_flush()
        exporter.clear()

        msg2 = types.Content(
            role="user", parts=[types.Part(text="How about London?")]
        )
        async for _event in runner.run_async(
            user_id="user1", session_id=session.id, new_message=msg2
        ):
            pass

        provider.force_flush()
        schemas = otel_spans_to_genai_schemas(exporter)
        msgs = build_chat_messages(schemas)

        user_msgs = [m for m in msgs if m.type == "user_message"]
        assert len(user_msgs) == 1, "Should have exactly one user message for this turn"
        assert "london" in user_msgs[0].text.lower(), \
            f"Should be about London, got: {user_msgs[0].text}"
    finally:
        uninstrument(proc)


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["localhost"],
)
@pytest.mark.asyncio
async def test_subagent_delegation(otel_setup):
    """Coordinator delegates to specialist sub_agents."""
    provider, exporter = otel_setup

    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    weather_agent = LlmAgent(
        name="WeatherAgent",
        model="gemini-2.0-flash",
        description="Weather specialist",
        instruction="Use get_weather.",
        tools=[_get_weather],
    )
    math_agent = LlmAgent(
        name="MathAgent",
        model="gemini-2.0-flash",
        description="Math specialist",
        instruction="Use calculator.",
        tools=[_calculator],
    )
    coordinator = LlmAgent(
        name="Coordinator",
        model="gemini-2.0-flash",
        description="Routes to specialists.",
        instruction="Delegate to WeatherAgent for weather, MathAgent for math.",
        sub_agents=[weather_agent, math_agent],
    )

    proc = instrument(provider, agents=[coordinator], capture_media=False)

    try:
        runner = InMemoryRunner(agent=coordinator, app_name="test_app")
        session = await runner.session_service.create_session(
            app_name="test_app", user_id="user1"
        )

        user_msg = types.Content(
            role="user", parts=[types.Part(text="What is 42 * 17?")]
        )
        async for _event in runner.run_async(
            user_id="user1", session_id=session.id, new_message=user_msg
        ):
            pass

        provider.force_flush()
        schemas = otel_spans_to_genai_schemas(exporter)
        msgs = build_chat_messages(schemas)

        assert any(m.type == "user_message" for m in msgs), "Should have user message"
        assert any(m.type in {"tool_call", "agent_message"} for m in msgs), \
            "Should have either a tool call or agent response"
    finally:
        uninstrument(proc)
