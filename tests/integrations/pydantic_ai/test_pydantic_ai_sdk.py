"""
Integration tests for the PydanticAI SDK and its tracing functionality.

This module contains tests that verify the correct patching of the PydanticAI Agent,
the capture and export of OpenTelemetry traces, and the correct conversion of those
traces into Weave's internal call schema. The tests ensure that both PydanticAI agent
calls and underlying OpenAI calls are properly traced, related, and validated for
correctness in the Weave trace server.

Fixtures and utilities are provided to create test clients, process OTLP spans, and
validate the relationships and attributes of captured traces.
"""

from typing import Any, cast

import pytest

from weave.trace_server import trace_server_interface as tsi


def verify_pydantic_ai_traces(
    calls: list[tsi.CallSchema], query_text: str, expected_response_text: str
) -> tuple[tsi.CallSchema, tsi.CallSchema]:
    """
    Verify that PydanticAI traces were correctly captured and converted.

    This function checks:
    - That both PydanticAI and OpenAI calls are present and related
    - That span relationships and timing are correct
    - That key attributes, inputs, and outputs are preserved and mapped
    - That token usage is tracked and calculated as expected

    Args:
        calls: list of CallSchema objects from calls_query
        query_text: The text of the query that was sent (e.g., "What is the capital of France?")
        expected_response_text: Text expected in the response (e.g., "Paris")

    Returns:
        tuple: (pydantic_ai_call, openai_call) - The relevant call objects for further testing
    """
    assert len(calls) >= 2, f"Expected at least 2 calls, found {len(calls)}"

    pydantic_ai_calls = [
        call
        for call in calls
        if "agent run" in call.op_name or "pydantic_ai.Agent.run_sync" in call.op_name
    ]
    assert (
        len(pydantic_ai_calls) == 1
    ), f"Expected 1 PydanticAI call, found {len(pydantic_ai_calls)}"
    pydantic_ai_call = pydantic_ai_calls[0]

    openai_calls = [
        call
        for call in calls
        if "openai" in call.op_name.lower() or "gpt" in call.op_name.lower()
    ]
    assert (
        len(openai_calls) > 0
    ), "No OpenAI calls were found, but PydanticAI should make OpenAI calls"
    openai_call = openai_calls[0]

    # Relationship and timing checks
    assert (
        pydantic_ai_call.trace_id == openai_call.trace_id
    ), "Trace IDs should match between PydanticAI and OpenAI calls"
    assert pydantic_ai_call.id != openai_call.id, "Span IDs should be different"
    assert (
        pydantic_ai_call.started_at <= openai_call.started_at
    ), "PydanticAI call should start before or at the same time as OpenAI call"
    assert (
        pydantic_ai_call.ended_at >= openai_call.ended_at
    ), "PydanticAI call should end after or at the same time as OpenAI call"

    # Attribute and input/output checks
    assert pydantic_ai_call.attributes.get(
        "otel_span"
    ), "OTEL span data should be preserved in attributes"
    otel_attrs = cast(
        dict[str, Any], pydantic_ai_call.attributes["otel_span"].get("attributes", {})
    )
    assert (
        "agent_name" in otel_attrs or "model_name" in otel_attrs
    ), "Expected PydanticAI attributes not found"

    assert pydantic_ai_call.inputs, "Inputs should be present"
    assert (
        "gen_ai.prompt" in pydantic_ai_call.inputs
    ), "gen_ai.prompt should be present in inputs"
    prompt_contains_query = any(
        query_text in str(msg.get("content", ""))
        for msg in pydantic_ai_call.inputs.get("gen_ai.prompt", [])
    )
    assert prompt_contains_query, f"Query text '{query_text}' not found in the prompt"

    assert pydantic_ai_call.output, "Outputs should be present"
    assert (
        "gen_ai.completion" in pydantic_ai_call.output
    ), "gen_ai.completion should be present in output"
    completion_content = (
        cast(dict[str, Any], pydantic_ai_call.output)
        .get("gen_ai.completion", {})
        .get("content", "")
    )
    assert (
        expected_response_text in completion_content
    ), f"Expected text '{expected_response_text}' not found in the completion"

    # Token usage checks
    assert pydantic_ai_call.summary, "Summary should be present"
    assert "usage" in pydantic_ai_call.summary, "Usage should be present in summary"
    usage_key = next(
        iter(cast(dict[str, Any], pydantic_ai_call.summary).get("usage", {})), ""
    )
    usage = cast(dict[str, Any], pydantic_ai_call.summary)["usage"].get(usage_key, {})
    assert usage.get("prompt_tokens") is not None, "Prompt tokens should be present"
    assert (
        usage.get("completion_tokens") is not None
    ), "Completion tokens should be present"
    if usage.get("total_tokens") is not None:
        expected_total = (usage.get("prompt_tokens") or 0) + (
            usage.get("completion_tokens") or 0
        )
        assert (
            usage.get("total_tokens") == expected_total
        ), "Total tokens should be the sum of prompt and completion tokens"

    return pydantic_ai_call, openai_call


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "api.openai.com", "trace.wandb.ai"],
)
def test_pydantic_ai_agent_patching(pydantic_ai_client_creator: Any) -> None:
    """
    Test that the PydanticAI Agent is properly patched and trace calls are captured.

    This test verifies that:
    1. The OpenAI patcher is correctly reset
    2. A PydanticAI Agent can be created and instrumented
    3. The agent can process a simple query successfully
    4. OTEL spans are properly exported to the trace server
    5. The trace contains expected PydanticAI and OpenAI calls

    Args:
        pydantic_ai_client_creator: A fixture that provides a context manager
            which yields a client with mocked PydanticAISpanExporter for testing

    Returns:
        None
    """
    with pydantic_ai_client_creator() as client:
        from pydantic_ai import Agent
        from weave.integrations.openai.openai_sdk import get_openai_patcher

        get_openai_patcher().undo_patch()
        agent = Agent("openai:gpt-4o")
        query_text = "What is the capital of France?"
        result = agent.run_sync(query_text)
        expected_response_text = "Paris"
        assert expected_response_text in result.output

        # Export spans and verify trace relationships and content
        client.process_otel_spans()
        project_id = client._project_id()
        res = client.server.calls_query(
            tsi.CallsQueryReq(
                project_id=project_id,
            )
        )
        assert (
            len(res.calls) > 0
        ), "No calls found in the server after sending OTEL spans"
        verify_pydantic_ai_traces(res.calls, query_text, expected_response_text)
