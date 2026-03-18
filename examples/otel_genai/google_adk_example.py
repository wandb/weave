# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "google-adk>=1.0",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
# ]
# ///
"""Google ADK with subagents, delegation, and tools — all OTel traced.

ADK has native OTel instrumentation.  This script creates a multi-agent
system with LLM-driven delegation:

  - Coordinator: triage agent that routes to specialists via sub_agents
  - WeatherAgent: looks up weather via a tool
  - MathAgent: performs arithmetic via a calculator tool
  - JokeAgent: tells jokes (pure LLM, no tools)

The coordinator decides which specialist to delegate to based on the
user's question.  Each delegation, tool call, and LLM generation becomes
a separate OTel span in a parent→child hierarchy.

Usage:
    uv run --python 3.12 google_adk_example.py
    uv run --python 3.12 google_adk_example.py --otlp-endpoint http://localhost:4317
    uv run --python 3.12 google_adk_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio
import os

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


def _wandb_auth_headers() -> dict[str, str]:
    """Build auth headers from WANDB_API_KEY if present."""
    api_key = os.environ.get("WANDB_API_KEY", "")
    if api_key:
        return {"wandb-api-key": api_key}
    return {}


def setup_otel(
    otlp_endpoint: str | None = None,
    genai_endpoint: str | None = None,
) -> TracerProvider:
    """Configure OTel TracerProvider. Must be called BEFORE importing ADK."""
    entity = os.environ.get("WANDB_ENTITY", "ben-urmomsclothes")
    resource = Resource.create(
        {
            "service.name": "google-adk-otel-example",
            "service.version": "0.1.0",
            "wandb.entity": entity,
            "wandb.project": "genai-otel-test",
        }
    )
    provider = TracerProvider(resource=resource)

    if genai_endpoint:
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
# Tools (defined before ADK imports since they're plain functions)
# ---------------------------------------------------------------------------

def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: Name of the city.

    Returns:
        Weather description string.
    """
    forecasts = {
        "san francisco": "Foggy, 58°F, wind 12 mph W",
        "tokyo": "Clear, 75°F, humidity 45%",
        "london": "Rainy, 52°F, wind 8 mph SW",
        "paris": "Overcast, 61°F, light drizzle",
        "barcelona": "Sunny, 82°F, UV index 7",
    }
    return forecasts.get(city.lower(), f"Partly cloudy, 68°F in {city}")


def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression safely.

    Args:
        expression: A mathematical expression like '42 * 17' or '(3 + 4) * 2'.

    Returns:
        The result as a string.
    """
    allowed = set("0123456789+-*/.(). ")
    if not all(c in allowed for c in expression):
        return f"Error: invalid characters in expression: {expression}"
    try:
        result = eval(expression)  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Agent construction (deferred to avoid importing ADK before OTel is set up)
# ---------------------------------------------------------------------------

def build_agents():
    """Build the multi-agent hierarchy. Call after OTel is configured."""
    from google.adk.agents import LlmAgent

    weather_agent = LlmAgent(
        name="WeatherAgent",
        model="gemini-2.0-flash",
        description="Specialist for weather forecasts and conditions in any city.",
        instruction=(
            "You are a weather specialist. Use the get_weather tool to look "
            "up weather for cities. Give a short, friendly answer."
        ),
        tools=[get_weather],
    )

    math_agent = LlmAgent(
        name="MathAgent",
        model="gemini-2.0-flash",
        description="Specialist for arithmetic calculations and math questions.",
        instruction=(
            "You are a math specialist. Use the calculator tool to evaluate "
            "arithmetic expressions. Show your work briefly."
        ),
        tools=[calculator],
    )

    joke_agent = LlmAgent(
        name="JokeAgent",
        model="gemini-2.0-flash",
        description="Specialist for telling jokes and being funny.",
        instruction=(
            "You are a comedian. Tell a short, clever joke related to the "
            "user's topic. Keep it to 2-3 sentences max."
        ),
    )

    coordinator = LlmAgent(
        name="Coordinator",
        model="gemini-2.0-flash",
        description="Routes requests to the appropriate specialist agent.",
        instruction=(
            "You are a helpful coordinator. Based on the user's request, "
            "delegate to the appropriate specialist:\n"
            "  - WeatherAgent for weather questions\n"
            "  - MathAgent for calculations and math\n"
            "  - JokeAgent for jokes and humor\n\n"
            "Always delegate — do not answer directly."
        ),
        sub_agents=[weather_agent, math_agent, joke_agent],
    )

    return coordinator


async def run_agents(coordinator) -> None:
    """Run multiple queries through the coordinator to exercise delegation."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=coordinator, app_name="multi_agent_app")

    queries = [
        "What's the weather in Tokyo and Paris?",
        "What is (42 * 17) + (256 / 8)?",
        "Tell me a joke about programming.",
    ]

    for q in queries:
        print(f"\n{'='*60}")
        print(f"User: {q}")
        print(f"{'='*60}")

        session = await runner.session_service.create_session(
            app_name="multi_agent_app",
            user_id="user1",
        )

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=q)],
        )

        async for event in runner.run_async(
            user_id="user1",
            session_id=session.id,
            new_message=user_message,
        ):
            if event.is_final_response() and event.content:
                text = event.content.parts[0].text.strip()
                print(f"\nAgent: {text}\n")


def main() -> None:
    """Entry point: parse args, set up OTel, build agents, run, flush."""
    parser = argparse.ArgumentParser(description="Google ADK OTel example")
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

    provider = setup_otel(args.otlp_endpoint, args.genai_endpoint)

    coordinator = build_agents()
    asyncio.run(run_agents(coordinator))

    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
