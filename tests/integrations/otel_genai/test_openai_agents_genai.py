"""Integration test: OpenAI Agents SDK -> OTel -> genai_otel_export -> verify normalization."""

import asyncio
import os

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from tests.trace.util import client_is_sqlite
from weave.trace import weave_client
from weave.trace_server import trace_server_interface as tsi

from .conftest import build_genai_export_req, find_spans_by_field

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY required"
    ),
]


def test_openai_agents_genai_normalization(
    client: weave_client.WeaveClient,
    fresh_exporter: InMemorySpanExporter,
) -> None:
    """Run an OpenAI agent with a tool call and verify GenAI span normalization."""
    if client_is_sqlite(client):
        pytest.skip("genai_otel_export requires ClickHouse")

    from agents import Agent, Runner, function_tool, set_trace_processors
    from openai_agents_opentelemetry import OpenTelemetryTracingProcessor

    @function_tool
    def get_weather(city: str) -> str:
        """Get the current weather for a city."""
        return f"Sunny, 72°F in {city}"

    otel_processor = OpenTelemetryTracingProcessor()
    set_trace_processors([otel_processor])

    agent = Agent(
        name="WeatherBot",
        instructions="You help users check the weather. Use the get_weather tool when asked. Give a short answer.",
        tools=[get_weather],
        model="gpt-4o-mini",
    )

    result = asyncio.run(
        Runner.run(agent, "What's the weather in San Francisco?")
    )
    assert result.final_output is not None

    otel_processor.force_flush()

    finished_spans = fresh_exporter.get_finished_spans()
    assert len(finished_spans) > 0, "No OTel spans were captured"

    project_id = client._project_id()
    export_req = build_genai_export_req(finished_spans, project_id)
    response = client.server.genai_otel_export(export_req)
    assert isinstance(response, tsi.OTelExportRes)
    assert response.partial_success is None

    query_res = client.server.genai_spans_query(
        tsi.GenAISpansQueryReq(project_id=project_id, limit=50)
    )
    assert len(query_res.spans) > 0, "No spans found after ingest"

    agent_spans = find_spans_by_field(
        query_res.spans, "operation_name", "invoke_agent"
    )
    assert len(agent_spans) >= 1, (
        f"Expected invoke_agent span, got ops: {[s.operation_name for s in query_res.spans]}"
    )
    assert agent_spans[0].agent_name == "WeatherBot"

    tool_spans = find_spans_by_field(
        query_res.spans, "operation_name", "execute_tool"
    )
    assert len(tool_spans) >= 1, (
        f"Expected execute_tool span, got ops: {[s.operation_name for s in query_res.spans]}"
    )
    assert tool_spans[0].tool_name == "get_weather"
