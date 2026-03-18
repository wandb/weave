# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai-agents",
#     "opentelemetry-instrumentation-openai-agents-v2",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
#     "weave @ file:///Users/ben/repos/core/services/weave-python/weave-public",
# ]
# ///
"""OpenAI Agents SDK with subagents, handoffs, and tools — all OTel traced.

Demonstrates a triage agent that routes to specialized subagents:
  - WeatherBot: checks weather via a tool
  - TravelAdvisor: looks up flights and hotels via tools
  - Translator: translates text (no tools, just LLM)

NOTE: System prompts / agent instructions are manually attached to spans
via gen_ai.system_instructions because the OpenAI Agents v2 OTel
instrumentor does not emit them. The OTel GenAI semantic conventions
define this attribute (merged in semantic-conventions PR #2179, Aug 2025)
but no instrumentor implements it yet:
  - https://github.com/open-telemetry/semantic-conventions/pull/2179
  - https://github.com/open-telemetry/opentelemetry-python-contrib/issues/4038

Usage:
    uv run --python 3.12 openai_agents_example.py
    uv run --python 3.12 openai_agents_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio
import os

from agents import Agent, Runner, function_tool

from weave.otel import SystemPromptInjector, setup_tracing

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


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
    """Search for available flights between two cities on a date."""
    return (
        f"Found 3 flights from {origin} to {destination} on {date}:\n"
        f"  1) UA 234 — departs 08:15, arrives 11:30 — $389\n"
        f"  2) DL 567 — departs 12:45, arrives 16:00 — $425\n"
        f"  3) AA 891 — departs 18:20, arrives 21:35 — $352"
    )


@function_tool
def search_hotels(city: str, checkin: str, checkout: str) -> str:
    """Search for available hotels in a city for given dates."""
    return (
        f"Found 2 hotels in {city} ({checkin} to {checkout}):\n"
        f"  1) Grand Plaza Hotel — $179/night — 4.5★\n"
        f"  2) City Center Inn — $129/night — 4.2★"
    )


# ---------------------------------------------------------------------------
# Agent instructions
# ---------------------------------------------------------------------------

TRIAGE_INSTRUCTIONS = (
    "You are a helpful concierge. Based on the user's request, hand off "
    "to the appropriate specialist:\n"
    "  - WeatherBot for weather questions\n"
    "  - TravelAdvisor for flight/hotel/trip planning\n"
    "  - Translator for translation requests\n\n"
    "If the request spans multiple domains, handle the most relevant one "
    "first. Always hand off — do not answer directly."
)

WEATHER_INSTRUCTIONS = (
    "You are a weather specialist. Use the get_weather tool to look up "
    "weather for any city the user asks about. Give a short, friendly answer."
)

TRAVEL_INSTRUCTIONS = (
    "You are a travel planning specialist. Use search_flights and "
    "search_hotels to help the user plan trips. Summarize options clearly. "
    "If the user hasn't specified dates, suggest reasonable ones."
)

TRANSLATOR_INSTRUCTIONS = (
    "You are a translation specialist. Translate the user's text into "
    "the requested language. If no target language is specified, translate "
    "to Spanish. Only output the translation, nothing else."
)

AGENT_INSTRUCTIONS = {
    "TriageAgent": TRIAGE_INSTRUCTIONS,
    "WeatherBot": WEATHER_INSTRUCTIONS,
    "TravelAdvisor": TRAVEL_INSTRUCTIONS,
    "Translator": TRANSLATOR_INSTRUCTIONS,
}

# ---------------------------------------------------------------------------
# Specialist agents
# ---------------------------------------------------------------------------

weather_agent = Agent(
    name="WeatherBot",
    instructions=WEATHER_INSTRUCTIONS,
    tools=[get_weather],
    model="gpt-4o-mini",
    handoff_description="Specialist for weather forecasts and conditions",
)

travel_agent = Agent(
    name="TravelAdvisor",
    instructions=TRAVEL_INSTRUCTIONS,
    tools=[search_flights, search_hotels],
    model="gpt-4o-mini",
    handoff_description="Specialist for flight and hotel bookings",
)

translator_agent = Agent(
    name="Translator",
    instructions=TRANSLATOR_INSTRUCTIONS,
    model="gpt-4o-mini",
    handoff_description="Specialist for translating text between languages",
)

triage_agent = Agent(
    name="TriageAgent",
    instructions=TRIAGE_INSTRUCTIONS,
    handoffs=[weather_agent, travel_agent, translator_agent],
    model="gpt-4o-mini",
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_agents() -> None:
    """Run a multi-turn scenario that exercises handoffs and tools."""
    queries = [
        "What's the weather like in Tokyo and Barcelona?",
        "I want to fly from San Francisco to Tokyo next Friday and need a hotel for 3 nights.",
        "Translate 'The weather is beautiful today' to Japanese.",
    ]

    for q in queries:
        print(f"\n{'=' * 60}")
        print(f"User: {q}")
        print(f"{'=' * 60}")
        result = await Runner.run(triage_agent, q)
        print(f"\nAgent: {result.final_output}\n")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="OpenAI Agents SDK OTel example")
    parser.add_argument("--otlp-endpoint", type=str, default=None)
    parser.add_argument("--genai-endpoint", type=str, default=None)
    args = parser.parse_args()

    os.environ.setdefault(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "span_and_event"
    )

    provider = setup_tracing(
        service_name="openai-agents-otel-example",
        project="genai-otel-test",
        genai_endpoint=args.genai_endpoint,
        otlp_endpoint=args.otlp_endpoint,
        processors=[SystemPromptInjector(AGENT_INSTRUCTIONS)],
    )

    from opentelemetry.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    OpenAIAgentsInstrumentor().instrument(tracer_provider=provider)

    asyncio.run(run_agents())
    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
