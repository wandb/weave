# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai-agents",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
#     "weave",
# ]
# ///
"""OpenAI Agents SDK — multi-turn conversation with compaction, all OTel traced.

Demonstrates:
  - Multi-turn conversation via SQLiteSession (context carries across turns)
  - Automatic context compaction via OpenAIResponsesCompactionSession
  - Subagent handoffs: TriageAgent routes to WeatherBot, TravelAdvisor, Translator
  - Tool calls within a persistent conversation
  - Automatic system prompt, tool definition, and reasoning token capture
  - Compaction tracking (weave.compaction.* attributes)
  - Conversation stitching via gen_ai.conversation.id

All of this is set up with a single ``instrument()`` call — agent metadata
(instructions, tools, handoffs) is auto-discovered from the Agent objects.

The conversation is designed so each turn builds on prior context:
  1. Ask about weather in Tokyo
  2. Follow up about Barcelona (requires knowing we're comparing cities)
  3. Ask for a trip recommendation (requires both weather results)
  4. Book flights to the recommended city (handoff to TravelAdvisor)
  5. Find a hotel there (requires knowing destination from turn 4)
  6. Translate the recommendation to Japanese (handoff to Translator)
  7. Summarize everything discussed (tests full context recall / compaction)

Usage:
    uv run --python 3.12 openai_agents_example.py
    uv run --python 3.12 openai_agents_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio

from agents import Agent, Runner, SQLiteSession, function_tool
from agents.memory import OpenAIResponsesCompactionSession

from weave.otel import setup_tracing
from weave.otel.instrumentors.openai_agents import instrument

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
        "paris": "Overcast, 61°F, light drizzle",
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
# Agents
# ---------------------------------------------------------------------------

weather_agent = Agent(
    name="WeatherBot",
    instructions=(
        "You are a weather specialist. Use the get_weather tool to look up "
        "weather for any city the user asks about. Give a short, friendly answer."
    ),
    tools=[get_weather],
    model="gpt-4o-mini",
    handoff_description="Specialist for weather forecasts and conditions",
)

travel_agent = Agent(
    name="TravelAdvisor",
    instructions=(
        "You are a travel planning specialist. Use search_flights and "
        "search_hotels to help the user plan trips. Summarize options clearly. "
        "If the user hasn't specified dates, suggest reasonable ones."
    ),
    tools=[search_flights, search_hotels],
    model="gpt-4o-mini",
    handoff_description="Specialist for flight and hotel bookings",
)

translator_agent = Agent(
    name="Translator",
    instructions=(
        "You are a translation specialist. Translate the user's text into "
        "the requested language. If no target language is specified, translate "
        "to Spanish. Only output the translation, nothing else."
    ),
    model="gpt-4o-mini",
    handoff_description="Specialist for translating text between languages",
)

triage_agent = Agent(
    name="TriageAgent",
    instructions=(
        "You are a helpful concierge. Based on the user's request, hand off "
        "to the appropriate specialist:\n"
        "  - WeatherBot for weather questions\n"
        "  - TravelAdvisor for flight/hotel/trip planning\n"
        "  - Translator for translation requests\n\n"
        "If the request spans multiple domains, handle the most relevant one "
        "first. Always hand off — do not answer directly."
    ),
    handoffs=[weather_agent, travel_agent, translator_agent],
    model="o4-mini",
)

# Multi-turn conversation: each turn builds on prior context
CONVERSATION = [
    "What's the weather like in Tokyo?",
    "How about Barcelona?",
    "Which city would be better for a beach day? Explain why.",
    "Book me a flight from San Francisco to whichever city you recommended, next Friday.",
    "And find me a hotel there for 3 nights starting that Friday.",
    "Translate your hotel recommendation into Japanese.",
    "Give me a brief summary of everything we've discussed in this conversation.",
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_conversation() -> None:
    """Run a multi-turn conversation with context carryover and compaction."""
    underlying = SQLiteSession("trip-planning-session")

    session = OpenAIResponsesCompactionSession(
        session_id="trip-planning-session",
        underlying_session=underlying,
    )

    for i, query in enumerate(CONVERSATION, 1):
        print(f"\n{'=' * 60}")
        print(f"Turn {i}/{len(CONVERSATION)}")
        print(f"User: {query}")
        print(f"{'=' * 60}")

        result = await Runner.run(triage_agent, query, session=session)
        print(f"\nAgent: {result.final_output}\n")

    items = await session.get_items()
    print(f"\n{'=' * 60}")
    print(f"Session has {len(items)} items after {len(CONVERSATION)} turns")
    print("(compaction reduces this from what would otherwise be much larger)")
    print(f"{'=' * 60}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="OpenAI Agents SDK OTel example")
    parser.add_argument("--otlp-endpoint", type=str, default=None)
    parser.add_argument("--genai-endpoint", type=str, default=None)
    args = parser.parse_args()

    provider = setup_tracing(
        service_name="openai-agents-otel-example",
        project="genai-otel-test",
        genai_endpoint=args.genai_endpoint,
        otlp_endpoint=args.otlp_endpoint,
    )

    # One call: auto-discovers instructions, tools, handoffs from the agent
    # tree. Also patches reasoning token capture, compaction tracking, and
    # sets up conversation stitching.
    instrument(provider, agents=[triage_agent], conversation="trip-planning")

    asyncio.run(run_conversation())
    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
