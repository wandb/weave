# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "claude-agent-sdk>=0.1.14",
#     "opentelemetry-instrumentation-claude-agent-sdk @ file:///tmp/otel-claude-instr/dist/opentelemetry_instrumentation_claude_agent_sdk-2.0b0.dev0-py3-none-any.whl",
#     "opentelemetry-api>=1.37.0",
#     "opentelemetry-sdk>=1.37.0",
#     "opentelemetry-instrumentation==0.58b0",
#     "opentelemetry-semantic-conventions==0.58b0",
#     "opentelemetry-util-genai>=0.2b0,<0.4b0",
#     "opentelemetry-exporter-otlp-proto-grpc",
#     "opentelemetry-exporter-otlp-proto-http",
#     "anyio",
# ]
#
# [tool.uv]
# prerelease = "allow"
# ///
"""Anthropic Claude Agent SDK with OTel tracing.

Uses the opentelemetry-instrumentation-claude-agent-sdk package (built from
source at /tmp/otel-claude-instr/) to auto-instrument the Claude Agent SDK.
The instrumentor monkey-patches InternalClient.process_query to create OTel
spans for agent invocations, chat turns, and tool executions.

Setup (one-time):
    git clone --depth 1 --sparse https://github.com/open-telemetry/opentelemetry-python-contrib.git /tmp/otel-claude-instr
    cd /tmp/otel-claude-instr && git sparse-checkout set instrumentation-genai/opentelemetry-instrumentation-claude-agent-sdk
    cd instrumentation-genai/opentelemetry-instrumentation-claude-agent-sdk && uv build

Usage:
    uv run --python 3.12 anthropic_example.py
    uv run --python 3.12 anthropic_example.py --otlp-endpoint http://localhost:4317
    uv run --python 3.12 anthropic_example.py --genai-endpoint http://localhost:6345/otel/v1/genai/traces
"""

import argparse
import os

import anyio
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPHTTPSpanExporter,
)
from opentelemetry.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor
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


async def run_agent() -> None:
    """Run a Claude agent that answers a question about travel."""
    os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

    options = ClaudeAgentOptions(
        agents={
            "assistant": AgentDefinition(
                description="A helpful travel assistant",
                prompt=(
                    "You are a concise travel assistant. "
                    "Answer questions about travel destinations briefly."
                ),
                model="sonnet",
            ),
        },
    )

    print("=== Claude Agent SDK Example ===")
    async for message in query(
        prompt="What are the top 3 things to do in Barcelona? Be very brief.",
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        elif (
            isinstance(message, ResultMessage)
            and message.total_cost_usd
            and message.total_cost_usd > 0
        ):
            print(f"\nCost: ${message.total_cost_usd:.4f}")
    print()


def main() -> None:
    """Entry point: parse args, set up OTel, run agent, flush."""
    parser = argparse.ArgumentParser(description="Anthropic Claude Agent SDK OTel example")
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
    ClaudeAgentSDKInstrumentor().instrument(tracer_provider=provider)

    anyio.run(run_agent)

    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
