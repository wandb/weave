"""Tests for Claude Agent SDK x Weave integration.

Uses recorded response cassettes replayed through a ReplayTransport,
analogous to VCR for HTTP-based integrations. The Claude Agent SDK
communicates via subprocess, so we replay at the Transport layer.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

import weave
from weave.integrations.claude_agent_sdk.claude_agent_sdk_integration import (
    get_claude_agent_sdk_patcher,
)
from weave.integrations.integration_utilities import op_name_from_call

from .conftest import ReplayTransport, load_cassette


@pytest.fixture(autouse=True)
def patch_claude_agent_sdk() -> Generator[None, None, None]:
    import weave.integrations.claude_agent_sdk.claude_agent_sdk_integration as mod

    mod._claude_agent_sdk_patcher = None
    patcher = get_claude_agent_sdk_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


# =====================================================================
# query() — simple text response
# =====================================================================


@pytest.mark.skip_clickhouse_client
@pytest.mark.asyncio
async def test_simple_text_query(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    cassette = load_cassette("simple_text_response")
    transport = ReplayTransport(cassette)

    messages = []
    async for msg in query(
        prompt="What is 2+2?",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        messages.append(msg)

    # Verify messages came through
    assert any(isinstance(m, AssistantMessage) for m in messages)
    assert any(isinstance(m, ResultMessage) for m in messages)

    result_msg = next(m for m in messages if isinstance(m, ResultMessage))
    assert result_msg.is_error is False
    assert result_msg.total_cost_usd == 0.003

    # Verify weave calls
    calls = list(client.get_calls())
    assert len(calls) == 1

    root_call = calls[0]
    assert op_name_from_call(root_call) == "claude_agent_sdk.query"
    assert root_call.inputs["prompt"] == "What is 2+2?"
    assert root_call.exception is None
    assert root_call.ended_at is not None

    output = root_call.output
    assert output["status"] == "completed"
    assert output["model"] == "claude-sonnet-4-6"
    assert output["usage"] == {"input_tokens": 25, "output_tokens": 10}
    assert output["total_cost_usd"] == 0.003
    assert output["num_turns"] == 1
    assert output["result"] == "The answer is 4."

    summary = root_call.summary
    assert summary is not None
    model_usage = summary["usage"]["claude-sonnet-4-6"]
    assert model_usage["requests"] == 1
    assert model_usage["input_tokens"] == 25
    assert model_usage["output_tokens"] == 10


# =====================================================================
# query() — tool use
# =====================================================================


@pytest.mark.skip_clickhouse_client
@pytest.mark.asyncio
async def test_tool_use_query(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    cassette = load_cassette("tool_use_response")
    transport = ReplayTransport(cassette)

    messages = []
    async for msg in query(
        prompt="List files in the current directory",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        messages.append(msg)

    assert any(isinstance(m, ResultMessage) for m in messages)

    # Verify weave calls: root + 1 tool use child
    calls = list(client.get_calls())
    assert len(calls) == 2

    root_call = next(
        c for c in calls if op_name_from_call(c) == "claude_agent_sdk.query"
    )
    tool_call = next(
        c for c in calls if op_name_from_call(c) == "claude_agent_sdk.tool_use.Bash"
    )

    # Root call
    assert root_call.output["status"] == "completed"
    assert root_call.output["model"] == "claude-sonnet-4-6"
    assert root_call.output["total_cost_usd"] == 0.008

    # Tool call is a child of root
    assert tool_call.parent_id == root_call.id
    assert tool_call.ended_at is not None
    assert tool_call.output is not None
    assert tool_call.output["tool_use_id"] == "toolu_01ABC"
    assert "file1.py" in tool_call.output["content"]


# =====================================================================
# query() — multiple tool uses in one message
# =====================================================================


@pytest.mark.skip_clickhouse_client
@pytest.mark.asyncio
async def test_multi_tool_query(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    cassette = load_cassette("multi_tool_response")
    transport = ReplayTransport(cassette)

    messages = []
    async for msg in query(
        prompt="Check files and directory",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        messages.append(msg)

    # Verify weave calls: root + 2 tool use children
    calls = list(client.get_calls())
    assert len(calls) == 3

    root_call = next(
        c for c in calls if op_name_from_call(c) == "claude_agent_sdk.query"
    )
    tool_calls = [
        c for c in calls if op_name_from_call(c).startswith("claude_agent_sdk.tool_use")
    ]
    assert len(tool_calls) == 2

    tool_names = {op_name_from_call(c) for c in tool_calls}
    assert "claude_agent_sdk.tool_use.Read" in tool_names
    assert "claude_agent_sdk.tool_use.Bash" in tool_names

    # Both are children of root
    for tc in tool_calls:
        assert tc.parent_id == root_call.id
        assert tc.ended_at is not None


# =====================================================================
# query() — thinking blocks
# =====================================================================


@pytest.mark.skip_clickhouse_client
@pytest.mark.asyncio
async def test_thinking_query(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    cassette = load_cassette("thinking_response")
    transport = ReplayTransport(cassette)

    messages = []
    async for msg in query(
        prompt="Think carefully about this",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        messages.append(msg)

    # Thinking messages should still be yielded to the caller
    assert any(isinstance(m, AssistantMessage) for m in messages)

    # Verify weave calls — no tool calls, just the root
    calls = list(client.get_calls())
    assert len(calls) == 1

    root_call = calls[0]
    assert root_call.output["status"] == "completed"
    assert root_call.output["result"] == "After careful consideration, the answer is 42."

    # Verify thinking was captured in messages
    output_msgs = root_call.output["messages"]
    # System + user prompt + assistant (with merged thinking + text)
    assert any(
        msg.get("role") == "assistant"
        for msg in output_msgs
    )


# =====================================================================
# query() — error response
# =====================================================================


@pytest.mark.skip_clickhouse_client
@pytest.mark.asyncio
async def test_error_query(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    cassette = load_cassette("error_response")
    transport = ReplayTransport(cassette)

    messages = []
    async for msg in query(
        prompt="This will fail",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        messages.append(msg)

    result_msg = next(m for m in messages if isinstance(m, ResultMessage))
    assert result_msg.is_error is True

    calls = list(client.get_calls())
    assert len(calls) == 1

    root_call = calls[0]
    assert root_call.output["status"] == "error"
    assert root_call.exception is not None
    assert "something went wrong" in root_call.exception


# =====================================================================
# ClaudeSDKClient — multi-turn conversation
# =====================================================================


@pytest.mark.skip_clickhouse_client
@pytest.mark.asyncio
async def test_multi_turn_client(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from claude_agent_sdk import ClaudeSDKClient

    cassette = load_cassette("multi_turn_response")
    transport = ReplayTransport(cassette)

    sdk_client = ClaudeSDKClient(
        options=ClaudeAgentOptions(),
        transport=transport,
    )
    await sdk_client.connect()

    # Turn 1
    await sdk_client.query("Hello")
    turn1_msgs = [msg async for msg in sdk_client.receive_response()]
    assert any(isinstance(m, ResultMessage) for m in turn1_msgs)

    # Turn 2
    await sdk_client.query("What is the capital of France?")
    turn2_msgs = [msg async for msg in sdk_client.receive_response()]
    assert any(isinstance(m, ResultMessage) for m in turn2_msgs)

    await sdk_client.disconnect()

    # Verify weave calls: 2 turns
    calls = list(client.get_calls())
    turn_calls = [c for c in calls if op_name_from_call(c) == "claude_agent_sdk.turn"]
    assert len(turn_calls) == 2

    # First turn
    t1 = turn_calls[0]
    assert t1.inputs["prompt"] == "Hello"
    assert t1.output["status"] == "completed"
    assert t1.output["model"] == "claude-sonnet-4-6"
    assert t1.ended_at is not None

    # Second turn
    t2 = turn_calls[1]
    assert t2.inputs["prompt"] == "What is the capital of France?"
    assert t2.output["status"] == "completed"
    assert t2.output["result"] == "The capital of France is Paris."


# =====================================================================
# Messages pass through unmodified
# =====================================================================


@pytest.mark.skip_clickhouse_client
@pytest.mark.asyncio
async def test_messages_pass_through(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """The integration should not alter messages yielded to the caller."""
    cassette = load_cassette("simple_text_response")
    transport = ReplayTransport(cassette)

    messages = []
    async for msg in query(
        prompt="What is 2+2?",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        messages.append(msg)

    # Should get: SystemMessage, AssistantMessage, ResultMessage
    assert len(messages) == 3

    assistant_msg = next(m for m in messages if isinstance(m, AssistantMessage))
    assert isinstance(assistant_msg.content[0], TextBlock)
    assert assistant_msg.content[0].text == "The answer is 4."
    assert assistant_msg.model == "claude-sonnet-4-6"


# =====================================================================
# Usage summary propagates correctly
# =====================================================================


@pytest.mark.skip_clickhouse_client
@pytest.mark.asyncio
async def test_usage_summary(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    cassette = load_cassette("tool_use_response")
    transport = ReplayTransport(cassette)

    async for _ in query(
        prompt="List files",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        pass

    calls = list(client.get_calls())
    root_call = next(
        c for c in calls if op_name_from_call(c) == "claude_agent_sdk.query"
    )

    summary = root_call.summary
    assert summary is not None
    assert "usage" in summary
    model_usage = summary["usage"]["claude-sonnet-4-6"]
    assert model_usage["requests"] == 1
    assert model_usage["input_tokens"] == 150
    assert model_usage["output_tokens"] == 75
