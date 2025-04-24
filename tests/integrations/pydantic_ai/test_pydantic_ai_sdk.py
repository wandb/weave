import pytest

from weave.trace_server import trace_server_interface as tsi


def verify_pydantic_ai_traces(calls, query_text, expected_response_text):
    """
    Verify that PydanticAI traces were correctly captured and converted.

    Args:
        calls: List of CallSchema objects from calls_query
        query_text: The text of the query that was sent (e.g., "What is the capital of France?")
        expected_response_text: Text expected in the response (e.g., "Paris")

    Returns:
        tuple: (pydantic_ai_call, openai_call) - The relevant call objects for further testing
    """
    # Check that we have at least two calls (PydanticAI and OpenAI)
    assert len(calls) >= 2, f"Expected at least 2 calls, found {len(calls)}"

    # Extract the PydanticAI agent call and OpenAI calls
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

    # 1. Verify call relationships
    assert (
        pydantic_ai_call.trace_id == openai_call.trace_id
    ), "Trace IDs should match between PydanticAI and OpenAI calls"
    assert pydantic_ai_call.id != openai_call.id, "Span IDs should be different"

    # Timing should make sense (OpenAI call should be within PydanticAI call's timeframe)
    assert (
        pydantic_ai_call.started_at <= openai_call.started_at
    ), "PydanticAI call should start before or at the same time as OpenAI call"
    assert (
        pydantic_ai_call.ended_at >= openai_call.ended_at
    ), "PydanticAI call should end after or at the same time as OpenAI call"

    # 2. Verify span transformation
    # Check that PydanticAI attributes were preserved
    assert pydantic_ai_call.attributes.get(
        "otel_span"
    ), "OTEL span data should be preserved in attributes"
    otel_attrs = pydantic_ai_call.attributes["otel_span"].get("attributes", {})

    # Check for key PydanticAI attributes
    assert (
        "agent_name" in otel_attrs or "model_name" in otel_attrs
    ), "Expected PydanticAI attributes not found"

    # 3. Verify input/output mapping
    # Check inputs
    assert pydantic_ai_call.inputs, "Inputs should be present"
    assert (
        "gen_ai.prompt" in pydantic_ai_call.inputs
    ), "gen_ai.prompt should be present in inputs"

    # Check for query text in inputs
    prompt_contains_query = any(
        query_text in str(msg.get("content", ""))
        for msg in pydantic_ai_call.inputs.get("gen_ai.prompt", [])
    )
    assert prompt_contains_query, f"Query text '{query_text}' not found in the prompt"

    # Check outputs
    assert pydantic_ai_call.output, "Outputs should be present"
    assert (
        "gen_ai.completion" in pydantic_ai_call.output
    ), "gen_ai.completion should be present in output"

    # Check for expected text in outputs
    completion_content = pydantic_ai_call.output.get("gen_ai.completion", {}).get(
        "content", ""
    )
    assert (
        expected_response_text in completion_content
    ), f"Expected text '{expected_response_text}' not found in the completion"

    # 4. Verify token usage
    assert pydantic_ai_call.summary, "Summary should be present"
    assert "usage" in pydantic_ai_call.summary, "Usage should be present in summary"

    # Get usage from the first usage key (could be model name or "usage")
    usage_key = next(iter(pydantic_ai_call.summary.get("usage", {})), "")
    usage = pydantic_ai_call.summary["usage"].get(usage_key, {})

    assert usage.get("prompt_tokens") is not None, "Prompt tokens should be present"
    assert (
        usage.get("completion_tokens") is not None
    ), "Completion tokens should be present"

    # Verify total tokens calculation if present
    if usage.get("total_tokens") is not None:
        expected_total = (usage.get("prompt_tokens") or 0) + (
            usage.get("completion_tokens") or 0
        )
        assert (
            usage.get("total_tokens") == expected_total
        ), "Total tokens should be the sum of prompt and completion tokens"


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "api.openai.com", "trace.wandb.ai"],
)
def test_pydantic_ai_agent_patching(pydantic_ai_client_creator) -> None:
    """Test that the PydanticAI Agent is patched and calls are traced."""
    with pydantic_ai_client_creator() as client:
        from pydantic_ai import Agent
        from weave.integrations.openai.openai_sdk import get_openai_patcher

        # Clean up any existing OpenAI patching
        get_openai_patcher().undo_patch()

        # Create an agent with explicit instrumentation
        agent = Agent("openai:gpt-4o")

        # The query text to search for in inputs
        query_text = "What is the capital of France?"

        # Run a query
        result = agent.run_sync(query_text)

        # Verify the result contains information about Paris
        expected_response_text = "Paris"
        assert expected_response_text in result.output

        # Process OTEL spans into the trace server
        client.process_otel_spans()

        # Verify the call was traced via the server
        project_id = client._project_id()
        res = client.server.calls_query(
            tsi.CallsQueryReq(
                project_id=project_id,
            )
        )

        # Verify that there is at least one call
        assert (
            len(res.calls) > 0
        ), "No calls found in the server after sending OTEL spans"

        # Use our verification utility to check the traces
        verify_pydantic_ai_traces(res.calls, query_text, expected_response_text)
