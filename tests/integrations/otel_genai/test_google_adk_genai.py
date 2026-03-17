"""Integration test: Google ADK -> OTel -> genai_otel_export -> verify normalization."""

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
        not os.getenv("GOOGLE_API_KEY"), reason="GOOGLE_API_KEY required"
    ),
]


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


def test_google_adk_genai_normalization(
    client: weave_client.WeaveClient,
    fresh_exporter: InMemorySpanExporter,
) -> None:
    """Run a Google ADK agent with a tool call and verify GenAI span normalization."""
    if client_is_sqlite(client):
        pytest.skip("genai_otel_export requires ClickHouse")

    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    async def _run() -> str:
        agent = LlmAgent(
            name="MathAgent",
            model="gemini-2.0-flash",
            instruction="You are a helpful math assistant. Use the calculator tool. Give a short answer.",
            tools=[calculator],
        )
        runner = InMemoryRunner(agent=agent, app_name="test_math_app")
        session = await runner.session_service.create_session(
            app_name="test_math_app",
            user_id="test-user",
        )
        final_text = ""
        async for event in runner.run_async(
            user_id="test-user",
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="What is 42 multiplied by 17?")],
            ),
        ):
            if event.is_final_response() and event.content:
                final_text = event.content.parts[0].text.strip()
        return final_text

    result = asyncio.run(_run())
    assert result, "Agent produced no output"

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
    assert agent_spans[0].agent_name == "MathAgent"

    tool_spans = find_spans_by_field(
        query_res.spans, "operation_name", "execute_tool"
    )
    assert len(tool_spans) >= 1, (
        f"Expected execute_tool span, got ops: {[s.operation_name for s in query_res.spans]}"
    )
    assert tool_spans[0].tool_name == "calculator"

    llm_spans = find_spans_by_field(
        query_res.spans, "operation_name", "generate_content"
    )
    if llm_spans:
        assert llm_spans[0].request_model == "gemini-2.0-flash"
        assert llm_spans[0].input_tokens > 0
        assert llm_spans[0].output_tokens > 0
        assert llm_spans[0].conversation_id != ""
        assert (
            "gcp" in llm_spans[0].provider_name
            or "gemini" in llm_spans[0].provider_name
        )
