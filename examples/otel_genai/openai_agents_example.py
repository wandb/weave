# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai-agents",
#     "openai-agents-opentelemetry",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
# ]
# ///
"""OpenAI Agents SDK with OTel tracing.

Runs a simple agent with a tool call and exports all OTel spans to the console
(or an OTLP endpoint) so you can inspect the exact semantic conventions emitted.

Usage:
    uv run --python 3.12 openai_agents_example.py
    uv run --python 3.12 openai_agents_example.py --otlp-endpoint http://localhost:4317
"""

import argparse
import asyncio

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from agents import Agent, Runner, function_tool, set_trace_processors
from openai_agents_opentelemetry import OpenTelemetryTracingProcessor


@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"Sunny, 72°F in {city}"


def setup_otel(otlp_endpoint: str | None = None) -> TracerProvider:
    """Configure the OTel TracerProvider with console or OTLP export."""
    resource = Resource.create(
        {
            "service.name": "openai-agents-otel-example",
            "service.version": "0.1.0",
        }
    )
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider


async def run_agent() -> None:
    """Create and run an agent that uses a weather tool."""
    agent = Agent(
        name="WeatherBot",
        instructions="You help users check the weather. Use the get_weather tool when asked about weather. Give a short answer.",
        tools=[get_weather],
        model="gpt-4o-mini",
    )

    result = await Runner.run(agent, "What's the weather in San Francisco?")
    print(f"\n--- Agent output ---\n{result.final_output}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAI Agents SDK OTel example")
    parser.add_argument(
        "--otlp-endpoint",
        type=str,
        default=None,
        help="OTLP gRPC endpoint (e.g. http://localhost:4317). Defaults to console export.",
    )
    args = parser.parse_args()

    provider = setup_otel(args.otlp_endpoint)

    otel_processor = OpenTelemetryTracingProcessor()
    set_trace_processors([otel_processor])

    asyncio.run(run_agent())
    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
