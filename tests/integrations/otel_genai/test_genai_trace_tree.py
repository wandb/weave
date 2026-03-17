"""Integration test: verify genai_spans_trace returns a valid parent-child tree."""

import asyncio
import os

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from tests.trace.util import client_is_sqlite
from weave.trace import weave_client
from weave.trace_server import trace_server_interface as tsi

from .conftest import build_genai_export_req

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
    return str(ops.get(operation, f"unknown operation: {operation}"))


def test_genai_trace_tree(
    client: weave_client.WeaveClient,
    fresh_exporter: InMemorySpanExporter,
) -> None:
    """Verify genai_spans_trace returns spans with valid parent-child relationships."""
    if client_is_sqlite(client):
        pytest.skip("genai_otel_export requires ClickHouse")

    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    async def _run() -> None:
        agent = LlmAgent(
            name="TreeTestAgent",
            model="gemini-2.0-flash",
            instruction="You are a math assistant. Use the calculator tool. Short answer.",
            tools=[calculator],
        )
        runner = InMemoryRunner(agent=agent, app_name="tree_test_app")
        session = await runner.session_service.create_session(
            app_name="tree_test_app",
            user_id="test-user",
        )
        async for _ in runner.run_async(
            user_id="test-user",
            session_id=session.id,
            new_message=types.Content(
                role="user", parts=[types.Part(text="What is 10 + 20?")]
            ),
        ):
            pass

    asyncio.run(_run())

    finished_spans = fresh_exporter.get_finished_spans()
    assert len(finished_spans) > 0, "No OTel spans were captured"

    project_id = client._project_id()
    export_req = build_genai_export_req(finished_spans, project_id)
    client.server.genai_otel_export(export_req)

    trace_ids = {s.context.trace_id for s in finished_spans}
    assert len(trace_ids) >= 1

    first_trace_id = next(iter(trace_ids))
    trace_id_hex = format(first_trace_id, "032x")

    trace_res = client.server.genai_spans_trace(
        tsi.GenAISpansTraceReq(
            project_id=project_id,
            trace_id=trace_id_hex,
        )
    )
    assert len(trace_res.spans) > 0, "No spans returned for trace"

    for i in range(1, len(trace_res.spans)):
        assert trace_res.spans[i].started_at >= trace_res.spans[i - 1].started_at

    span_ids = {s.span_id for s in trace_res.spans}
    root_spans = [s for s in trace_res.spans if s.parent_span_id == ""]
    assert len(root_spans) >= 1, "No root span found (parent_span_id='')"

    for span in trace_res.spans:
        if span.parent_span_id and span.parent_span_id != "":
            assert span.parent_span_id in span_ids, (
                f"Span {span.span_id} has parent {span.parent_span_id} not in trace"
            )
