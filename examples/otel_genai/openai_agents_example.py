# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai-agents",
#     "opentelemetry-instrumentation-openai-agents-v2",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
#     "requests",
# ]
# ///
"""OpenAI Agents SDK with subagents, handoffs, and tools — all OTel traced.

Demonstrates a triage agent that routes to specialized subagents:
  - WeatherBot: checks weather via a tool
  - TravelAdvisor: looks up flights and hotels via tools
  - Translator: translates text (no tools, just LLM)

The triage agent decides which specialist to hand off to based on the
user's question.  Each handoff, tool call, and LLM generation becomes
a separate OTel span, so you can see the full parent→child hierarchy
in any trace viewer.

Usage:
    uv run --python 3.12 openai_agents_example.py
    uv run --python 3.12 openai_agents_example.py --otlp-endpoint http://localhost:4317
    uv run --python 3.12 openai_agents_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio
import os

from agents import Agent, Runner, function_tool
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPHTTPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

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
# Specialist agents
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


# ---------------------------------------------------------------------------
# Triage agent (the orchestrator)
# ---------------------------------------------------------------------------

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
    model="gpt-4o-mini",
)


# ---------------------------------------------------------------------------
# OTel setup
# ---------------------------------------------------------------------------


def _wandb_auth_headers() -> dict[str, str]:
    """Build auth headers from WANDB_API_KEY if present."""
    api_key = os.environ.get("WANDB_API_KEY", "")
    if api_key:
        return {"wandb-api-key": api_key}
    return {}


# ---------------------------------------------------------------------------
# Inline LiveSpanProcessor — ships span-start events for real-time UI.
# When weave is installed as a package, use weave.otel.LiveSpanProcessor.
# ---------------------------------------------------------------------------

class _LiveSpanProcessor:
    """Sends lightweight span-start POSTs so the UI can show in-progress spans."""

    def __init__(self, endpoint: str, headers: dict[str, str] | None = None):
        from concurrent.futures import ThreadPoolExecutor
        self._endpoint = endpoint
        self._headers = headers or {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="live-span")

    def on_start(self, span, parent_context=None):
        try:
            import json as _json
            from datetime import datetime, timezone
            import requests as _req

            ctx = span.get_span_context()
            if not ctx or not ctx.is_valid:
                return
            resource = getattr(span, "resource", None)
            entity = resource.attributes.get("wandb.entity", "") if resource else ""
            project = resource.attributes.get("wandb.project", "") if resource else ""
            if not entity or not project:
                return
            parent = getattr(span, "parent", None)
            parent_id = format(parent.span_id, "016x") if parent and hasattr(parent, "span_id") else ""
            attrs = dict(span._attributes) if hasattr(span, "_attributes") and span._attributes else {}
            ns = span.start_time if hasattr(span, "start_time") and span.start_time else 0
            started = datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat() if ns else datetime.now(timezone.utc).isoformat()

            payload = {
                "project_id": f"{entity}/{project}",
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
                "parent_span_id": parent_id,
                "span_name": span.name or "",
                "operation_name": str(attrs.get("gen_ai.operation.name", "")),
                "agent_name": str(attrs.get("gen_ai.agent.name", "")),
                "request_model": str(attrs.get("gen_ai.request.model", "")),
                "started_at": started,
            }

            def _post():
                try:
                    _req.post(self._endpoint, json=payload,
                              headers={"Content-Type": "application/json", **self._headers}, timeout=5)
                except Exception:
                    pass
            self._executor.submit(_post)
        except Exception:
            pass

    def on_end(self, span):
        pass

    def shutdown(self):
        self._executor.shutdown(wait=False)

    def force_flush(self, timeout_millis=None):
        return True


def setup_otel(
    otlp_endpoint: str | None = None,
    genai_endpoint: str | None = None,
) -> TracerProvider:
    """Configure the OTel TracerProvider with console, OTLP, or GenAI endpoint export."""
    entity = os.environ.get("WANDB_ENTITY", "ben-urmomsclothes")
    resource = Resource.create(
        {
            "service.name": "openai-agents-otel-example",
            "service.version": "0.1.0",
            "wandb.entity": entity,
            "wandb.project": "genai-otel-test",
        }
    )
    provider = TracerProvider(resource=resource)

    if genai_endpoint:
        server_url = genai_endpoint.rsplit("/otel/", 1)[0]
        provider.add_span_processor(
            _LiveSpanProcessor(
                endpoint=f"{server_url}/otel/v1/genai/span/start",
                headers=_wandb_auth_headers(),
            )
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPHTTPSpanExporter(
                    endpoint=genai_endpoint,
                    headers=_wandb_auth_headers(),
                )
            )
        )
    elif otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider


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
    """Entry point: parse args, set up OTel, run agents, flush."""
    parser = argparse.ArgumentParser(description="OpenAI Agents SDK OTel example")
    parser.add_argument(
        "--otlp-endpoint",
        type=str,
        default=None,
        help="OTLP gRPC endpoint (e.g. http://localhost:4317). Defaults to console export.",
    )
    parser.add_argument(
        "--genai-endpoint",
        type=str,
        default=None,
        help="Weave GenAI OTel HTTP endpoint (e.g. http://localhost:6345/otel/v1/genai/traces).",
    )
    args = parser.parse_args()

    os.environ.setdefault(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "span_and_event"
    )

    provider = setup_otel(args.otlp_endpoint, args.genai_endpoint)

    from opentelemetry.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    OpenAIAgentsInstrumentor().instrument(tracer_provider=provider)

    asyncio.run(run_agents())
    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
