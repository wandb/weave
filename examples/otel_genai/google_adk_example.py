# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "google-adk",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
# ]
# ///
"""Google Agent Development Kit (ADK) with OTel tracing.

ADK has native OTel instrumentation -- setting a global TracerProvider before
running an agent is all that's needed. This script creates a simple agent with
a calculator tool and exports all spans to the console (or OTLP endpoint).

Usage:
    uv run --python 3.12 google_adk_example.py
    uv run --python 3.12 google_adk_example.py --otlp-endpoint http://localhost:4317
    uv run --python 3.12 google_adk_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import asyncio

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


def setup_otel(
    otlp_endpoint: str | None = None,
    genai_endpoint: str | None = None,
) -> TracerProvider:
    """Configure the OTel TracerProvider with console, OTLP, or GenAI endpoint export.

    Must be called BEFORE importing any ADK components so the global
    TracerProvider is picked up by ADK's module-level tracer.
    """
    resource = Resource.create(
        {
            "service.name": "google-adk-otel-example",
            "service.version": "0.1.0",
            "wandb.entity": "ben-urmomsclothes",
            "wandb.project": "genai-otel-test",
        }
    )
    provider = TracerProvider(resource=resource)

    if genai_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPHTTPSpanExporter(endpoint=genai_endpoint))
        )
    elif otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider


def calculator(a: float, b: float, operation: str) -> str:
    """Perform a basic arithmetic operation.

    Args:
        a: First number.
        b: Second number.
        operation: One of 'add', 'subtract', 'multiply', 'divide'.

    Returns:
        The result as a string.
    """
    ops = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": a / b if b != 0 else "error: division by zero",
    }
    result = ops.get(operation, f"unknown operation: {operation}")
    return str(result)


async def run_agent() -> None:
    """Create and run a Google ADK agent with a calculator tool."""
    # Deferred imports so the global TracerProvider is already set
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = LlmAgent(
        name="MathAgent",
        model="gemini-2.0-flash",
        instruction="You are a helpful math assistant. Use the calculator tool to solve arithmetic problems. Give a short answer.",
        tools=[calculator],
    )

    runner = InMemoryRunner(agent=agent, app_name="math_app")

    session = await runner.session_service.create_session(
        app_name="math_app",
        user_id="user1",
    )

    user_message = types.Content(
        role="user",
        parts=[types.Part(text="What is 42 multiplied by 17?")],
    )

    async for event in runner.run_async(
        user_id="user1",
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content:
            text = event.content.parts[0].text.strip()
            print(f"\n--- Agent output ---\n{text}\n")


def main() -> None:
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

    asyncio.run(run_agent())
    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
