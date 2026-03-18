# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "anthropic",
#     "opentelemetry-instrumentation-anthropic",
#     "opentelemetry-sdk",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
# ]
# ///
"""Anthropic SDK with OTel tracing via Traceloop's instrumentor.

Uses the opentelemetry-instrumentation-anthropic package to auto-instrument
the anthropic client. Runs a multi-turn tool-use conversation to exercise
the full span hierarchy.

Usage:
    uv run --python 3.12 anthropic_example.py
    uv run --python 3.12 anthropic_example.py --otlp-endpoint http://localhost:4317
    uv run --python 3.12 anthropic_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import json
import os

import anthropic
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPHTTPSpanExporter,
)
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. 'San Francisco'",
                }
            },
            "required": ["city"],
        },
    }
]


def handle_tool_call(tool_name: str, tool_input: dict) -> str:
    """Simulate tool execution for the get_weather tool."""
    if tool_name == "get_weather":
        city = tool_input.get("city", "Unknown")
        return json.dumps({"city": city, "temperature": "72°F", "condition": "Sunny"})
    return json.dumps({"error": f"Unknown tool: {tool_name}"})


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
    """Configure the OTel TracerProvider with console, OTLP, or GenAI endpoint export."""
    entity = os.environ.get("WANDB_ENTITY", "ben-urmomsclothes")
    resource = Resource.create(
        {
            "service.name": "anthropic-otel-example",
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


def run_tool_use_conversation() -> None:
    """Run a multi-turn conversation with tool use against the Anthropic API."""
    client = anthropic.Anthropic()
    model = "claude-sonnet-4-20250514"

    messages: list[dict] = [
        {"role": "user", "content": "What's the weather in San Francisco?"}
    ]

    response = client.messages.create(
        model=model,
        max_tokens=256,
        tools=TOOLS,
        messages=messages,
    )

    if response.stop_reason == "tool_use":
        tool_use_block = next(b for b in response.content if b.type == "tool_use")

        tool_result = handle_tool_call(tool_use_block.name, tool_use_block.input)

        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": tool_result,
                    }
                ],
            }
        )

        final_response = client.messages.create(
            model=model,
            max_tokens=256,
            tools=TOOLS,
            messages=messages,
        )

        text = next(
            (b.text for b in final_response.content if hasattr(b, "text")), ""
        )
        print(f"\n--- Agent output ---\n{text}\n")
    else:
        text = next((b.text for b in response.content if hasattr(b, "text")), "")
        print(f"\n--- Agent output ---\n{text}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Anthropic SDK OTel example")
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
    AnthropicInstrumentor().instrument(tracer_provider=provider)

    run_tool_use_conversation()

    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
