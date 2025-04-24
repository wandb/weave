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
        calls: List of CallSchema objects from calls_query.
        query_text: The text of the query that was sent (e.g., "What is the capital of France?").
        expected_response_text: Text expected in the response (e.g., "Paris").

    Returns:
        tuple[tsi.CallSchema, tsi.CallSchema]: The relevant call objects for further testing.
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


def verify_tool_call_traces(
    calls: list[tsi.CallSchema],
    query_text: str,
    expected_tool_name: str,
    expected_tool_args: dict[str, Any],
    expected_tool_result: Any,
) -> tuple[tsi.CallSchema, tsi.CallSchema, tsi.CallSchema]:
    """
    Verify that PydanticAI tool call traces were correctly captured and converted.

    Args:
        calls: List of CallSchema objects from calls_query.
        query_text: The text of the query that triggered tool use.
        expected_tool_name: The name of the tool that should be called.
        expected_tool_args: The arguments expected to be passed to the tool.
        expected_tool_result: The expected result from the tool call.

    Returns:
        tuple[tsi.CallSchema, tsi.CallSchema, tsi.CallSchema]: The relevant call objects.
    """
    assert len(calls) >= 3, f"Expected at least 3 calls, found {len(calls)}"
    pydantic_ai_call, openai_call = verify_pydantic_ai_traces(
        calls, query_text, str(expected_tool_result)
    )
    tool_calls = [
        call
        for call in calls
        if (
            expected_tool_name in call.op_name
            or (
                call.display_name is not None
                and expected_tool_name in call.display_name
            )
            or call.op_name == "running tool"
        )
    ]
    assert (
        len(tool_calls) >= 1
    ), f"Expected at least 1 tool call for {expected_tool_name}, found {len(tool_calls)}"
    tool_call = None
    for call in tool_calls:
        if call.inputs and any(
            expected_tool_name in str(val)
            for val in call.attributes.get("otel_span", {})
            .get("attributes", {})
            .values()
        ):
            tool_call = call
            break
        if call.inputs and all(
            arg_name in str(call.inputs) for arg_name in expected_tool_args.keys()
        ):
            tool_call = call
            break
    if tool_call is None and tool_calls:
        for call in tool_calls:
            if call.inputs and any(
                str(arg_value) in str(call.inputs)
                for arg_value in expected_tool_args.values()
            ):
                tool_call = call
                break
    if tool_call is None and tool_calls:
        tool_call = tool_calls[0]
    assert (
        tool_call is not None
    ), f"Could not identify the specific tool call for {expected_tool_name} with args {expected_tool_args}"
    assert (
        tool_call.trace_id == pydantic_ai_call.trace_id
    ), "Tool call should be in same trace as PydanticAI call"
    assert (
        pydantic_ai_call.started_at <= tool_call.started_at
    ), "Tool call should start after agent call"
    assert (
        pydantic_ai_call.ended_at >= tool_call.ended_at
    ), "Tool call should end before agent call ends"
    input_found = False
    if tool_call.inputs:
        if any("input.value" in k for k in tool_call.inputs.keys()):
            input_value = tool_call.inputs.get("input.value", {})
            if isinstance(input_value, dict):
                for arg_name, arg_value in expected_tool_args.items():
                    assert (
                        arg_name in input_value
                    ), f"Expected argument {arg_name} not found in tool inputs"
                    assert (
                        input_value[arg_name] == arg_value
                    ), f"Expected {arg_name}={arg_value}, got {input_value[arg_name]}"
                input_found = True
        else:
            for arg_name, arg_value in expected_tool_args.items():
                if arg_name in tool_call.inputs:
                    assert (
                        tool_call.inputs[arg_name] == arg_value
                    ), f"Expected {arg_name}={arg_value}, got {tool_call.inputs[arg_name]}"
                    input_found = True
    if not input_found and "otel_span" in tool_call.attributes:
        otel_attrs = tool_call.attributes["otel_span"].get("attributes", {})
        if (
            "input" in otel_attrs
            and isinstance(otel_attrs["input"], dict)
            and "value" in otel_attrs["input"]
        ):
            input_value = otel_attrs["input"]["value"]
            for arg_name, arg_value in expected_tool_args.items():
                assert (
                    arg_name in input_value
                ), f"Expected argument {arg_name} not found in tool attributes"
                assert (
                    input_value[arg_name] == arg_value
                ), f"Expected {arg_name}={arg_value}, got {input_value[arg_name]}"
            input_found = True
    assert input_found, f"Could not find expected tool arguments {expected_tool_args} in either inputs or attributes"
    return pydantic_ai_call, openai_call, tool_call


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "api.openai.com", "trace.wandb.ai"],
)
def test_pydantic_ai_tool_calls(pydantic_ai_client_creator: Any) -> None:
    """
    Test that PydanticAI tool calls are properly traced and captured.

    This test verifies that:
    1. A PydanticAI Agent with a tool can be created and instrumented
    2. The agent can process a query that requires tool use
    3. The tool call is properly traced and related to the agent call
    4. Tool inputs and outputs are correctly captured in traces

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
        agent = Agent(
            "openai:gpt-4o",
            system_prompt=(
                "You are a helpful assistant that can multiply numbers. "
                "When asked to multiply numbers, use the multiply tool."
            ),
        )

        @agent.tool_plain
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        query_text = "What is 7 multiplied by 8?"
        result = agent.run_sync(query_text)
        expected_tool_name = "multiply"
        expected_tool_args = {"a": 7, "b": 8}
        expected_tool_result = 56
        assert str(expected_tool_result) in result.output
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
        verify_tool_call_traces(
            res.calls,
            query_text,
            expected_tool_name,
            expected_tool_args,
            expected_tool_result,
        )
