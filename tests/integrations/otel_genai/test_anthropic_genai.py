"""Integration test: Anthropic SDK -> OTel -> genai_otel_export -> verify normalization."""

import json
import os

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from tests.trace.util import client_is_sqlite
from weave.trace import weave_client
from weave.trace_server import trace_server_interface as tsi

from .conftest import _SESSION_PROVIDER, build_genai_export_req

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY required"
    ),
]

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


def test_anthropic_genai_normalization(
    client: weave_client.WeaveClient,
    fresh_exporter: InMemorySpanExporter,
) -> None:
    """Run a multi-turn Anthropic tool-use conversation and verify normalization."""
    if client_is_sqlite(client):
        pytest.skip("genai_otel_export requires ClickHouse")

    import anthropic
    from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor

    AnthropicInstrumentor().instrument(tracer_provider=_SESSION_PROVIDER)

    try:
        api_client = anthropic.Anthropic()
        model = "claude-sonnet-4-20250514"

        messages: list[dict] = [
            {"role": "user", "content": "What's the weather in San Francisco?"}
        ]

        response = api_client.messages.create(
            model=model, max_tokens=256, tools=TOOLS, messages=messages
        )

        if response.stop_reason == "tool_use":
            tool_use_block = next(
                b for b in response.content if b.type == "tool_use"
            )
            tool_result = json.dumps(
                {"city": "San Francisco", "temperature": "72°F", "condition": "Sunny"}
            )
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
            final_response = api_client.messages.create(
                model=model, max_tokens=256, tools=TOOLS, messages=messages
            )
            assert any(
                hasattr(b, "text") and b.text for b in final_response.content
            ), "No text in final response"

        finished_spans = fresh_exporter.get_finished_spans()
        assert len(finished_spans) > 0, "No OTel spans were captured"

        project_id = client._project_id()
        export_req = build_genai_export_req(finished_spans, project_id)
        resp = client.server.genai_otel_export(export_req)
        assert isinstance(resp, tsi.OTelExportRes)
        assert resp.partial_success is None

        query_res = client.server.genai_spans_query(
            tsi.GenAISpansQueryReq(project_id=project_id, limit=50)
        )
        assert len(query_res.spans) > 0, "No spans found after ingest"

        for span in query_res.spans:
            assert "anthropic" in span.provider_name.lower(), (
                f"Expected provider containing 'anthropic', got '{span.provider_name}'"
            )
            assert span.request_model == model
            assert span.input_tokens > 0
            assert span.output_tokens > 0

    finally:
        AnthropicInstrumentor().uninstrument()
