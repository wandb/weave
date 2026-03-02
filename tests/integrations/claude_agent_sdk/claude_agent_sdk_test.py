from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from weave.integrations.claude_agent_sdk import get_claude_agent_sdk_patcher
from weave.trace.weave_client import WeaveClient


def _op_name_matches(call_op_name: str, expected: str) -> bool:
    """Check that an op name URI contains the expected op name portion."""
    return f"/op/{expected}:" in call_op_name or call_op_name.endswith(f"/op/{expected}")


@pytest.fixture(autouse=True)
def patch_claude_agent_sdk() -> Generator[None, None, None]:
    patcher = get_claude_agent_sdk_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


def _make_text_block(text: str) -> object:
    from claude_agent_sdk import TextBlock

    return TextBlock(text=text)


def _make_tool_use_block(
    id: str, name: str, input: dict
) -> object:
    from claude_agent_sdk import ToolUseBlock

    return ToolUseBlock(id=id, name=name, input=input)


def _make_tool_result_block(
    tool_use_id: str, content: str | None = None, is_error: bool | None = None
) -> object:
    from claude_agent_sdk import ToolResultBlock

    return ToolResultBlock(tool_use_id=tool_use_id, content=content, is_error=is_error)


def _make_assistant_message(
    content: list, model: str = "claude-sonnet-4-20250514"
) -> object:
    from claude_agent_sdk import AssistantMessage

    return AssistantMessage(
        content=content, model=model, parent_tool_use_id=None, error=None
    )


def _make_user_message(content: str) -> object:
    from claude_agent_sdk import UserMessage

    return UserMessage(
        content=content, uuid=None, parent_tool_use_id=None, tool_use_result=None
    )


def _make_result_message(
    duration_ms: int = 1000,
    duration_api_ms: int = 800,
    is_error: bool = False,
    num_turns: int = 1,
    session_id: str = "default",
    total_cost_usd: float | None = 0.01,
    usage: dict | None = None,
    result: str | None = None,
) -> object:
    from claude_agent_sdk import ResultMessage

    if usage is None:
        usage = {"input_tokens": 100, "output_tokens": 50}
    return ResultMessage(
        subtype="result",
        duration_ms=duration_ms,
        duration_api_ms=duration_api_ms,
        is_error=is_error,
        num_turns=num_turns,
        session_id=session_id,
        total_cost_usd=total_cost_usd,
        usage=usage,
        result=result,
        structured_output=None,
    )


async def _run_conversation(messages: list, prompt: str = "Hello") -> list:
    """Helper to run a mocked conversation through the patched SDK client."""
    from claude_agent_sdk import ClaudeSDKClient

    async def fake_receive_response():
        for msg in messages:
            yield msg

    with patch.object(
        ClaudeSDKClient, "__init__", ClaudeSDKClient.__init__
    ):
        client = object.__new__(ClaudeSDKClient)
        # Set up the mock state expected by patched __init__
        client.query = AsyncMock()
        client.receive_response = fake_receive_response
        # Now call patched __init__ which wraps these methods
        ClaudeSDKClient.__init__(client)  # noqa: PLC2801

        # Run the conversation
        await client.query(prompt)
        result = []
        async for msg in client.receive_response():
            result.append(msg)
        return result


@pytest.mark.asyncio
async def test_simple_conversation(client: WeaveClient) -> None:
    """User prompt + single text response + ResultMessage."""
    messages = [
        _make_assistant_message([_make_text_block("Hello! How can I help?")]),
        _make_result_message(
            usage={"input_tokens": 10, "output_tokens": 20},
            total_cost_usd=0.005,
        ),
    ]

    await _run_conversation(messages, prompt="Hello")

    calls = list(client.get_calls())
    assert len(calls) == 2

    # Root call
    root = calls[0]
    assert _op_name_matches(root.op_name, "claude_agent_sdk.ClaudeSDKClient.conversation")
    assert root.inputs["prompt"] == "Hello"
    assert root.output["status"] == "completed"
    assert root.output["usage"] == {"input_tokens": 10, "output_tokens": 20}
    assert root.output["total_cost_usd"] == 0.005
    assert root.parent_id is None

    # LLM child call
    llm_call = calls[1]
    assert _op_name_matches(llm_call.op_name, "claude_agent_sdk.response")
    assert llm_call.output["text"] == "Hello! How can I help?"
    assert llm_call.parent_id == root.id


@pytest.mark.asyncio
async def test_tool_use_conversation(client: WeaveClient) -> None:
    """User prompt + tool use + tool result + text response."""
    messages = [
        _make_assistant_message([
            _make_tool_use_block("tool_1", "get_weather", {"city": "NYC"}),
        ]),
        _make_assistant_message([
            _make_tool_result_block("tool_1", content="Sunny, 72F"),
        ]),
        _make_assistant_message([
            _make_text_block("The weather in NYC is sunny and 72F!"),
        ]),
        _make_result_message(),
    ]

    await _run_conversation(messages, prompt="What's the weather in NYC?")

    calls = list(client.get_calls())
    assert len(calls) == 3

    root = calls[0]
    assert _op_name_matches(root.op_name, "claude_agent_sdk.ClaudeSDKClient.conversation")
    assert root.inputs["prompt"] == "What's the weather in NYC?"

    # Tool call
    tool_call = calls[1]
    assert _op_name_matches(tool_call.op_name, "claude_agent_sdk.tool_use.get_weather")
    assert tool_call.inputs["input"] == {"city": "NYC"}
    assert tool_call.output["content"] == "Sunny, 72F"
    assert tool_call.parent_id == root.id

    # LLM response
    llm_call = calls[2]
    assert _op_name_matches(llm_call.op_name, "claude_agent_sdk.response")
    assert llm_call.output["text"] == "The weather in NYC is sunny and 72F!"
    assert llm_call.parent_id == root.id


@pytest.mark.asyncio
async def test_multiple_tool_uses(client: WeaveClient) -> None:
    """User prompt + assistant with 2 tools + results + text."""
    messages = [
        _make_assistant_message([
            _make_tool_use_block("tool_1", "get_weather", {"city": "NYC"}),
            _make_tool_use_block("tool_2", "get_time", {"timezone": "EST"}),
        ]),
        _make_assistant_message([
            _make_tool_result_block("tool_1", content="Sunny, 72F"),
            _make_tool_result_block("tool_2", content="3:00 PM"),
        ]),
        _make_assistant_message([
            _make_text_block("NYC is sunny at 72F, and it's 3:00 PM EST."),
        ]),
        _make_result_message(),
    ]

    await _run_conversation(messages, prompt="Weather and time in NYC?")

    calls = list(client.get_calls())
    assert len(calls) == 4

    root = calls[0]
    assert _op_name_matches(root.op_name, "claude_agent_sdk.ClaudeSDKClient.conversation")

    # Two tool calls
    tool1 = calls[1]
    assert _op_name_matches(tool1.op_name, "claude_agent_sdk.tool_use.get_weather")
    assert tool1.inputs["input"] == {"city": "NYC"}
    assert tool1.output["content"] == "Sunny, 72F"

    tool2 = calls[2]
    assert _op_name_matches(tool2.op_name, "claude_agent_sdk.tool_use.get_time")
    assert tool2.inputs["input"] == {"timezone": "EST"}
    assert tool2.output["content"] == "3:00 PM"

    # LLM response
    llm_call = calls[3]
    assert _op_name_matches(llm_call.op_name, "claude_agent_sdk.response")


@pytest.mark.asyncio
async def test_multi_turn_conversation(client: WeaveClient) -> None:
    """Multiple assistant responses with text."""
    messages = [
        _make_assistant_message([_make_text_block("First response.")]),
        _make_assistant_message([_make_text_block("Second response.")]),
        _make_assistant_message([_make_text_block("Third response.")]),
        _make_result_message(num_turns=3),
    ]

    await _run_conversation(messages)

    calls = list(client.get_calls())
    assert len(calls) == 4  # root + 3 LLM calls

    root = calls[0]
    assert _op_name_matches(root.op_name, "claude_agent_sdk.ClaudeSDKClient.conversation")
    assert root.output["num_turns"] == 3

    for i, expected_text in enumerate(
        ["First response.", "Second response.", "Third response."]
    ):
        llm_call = calls[i + 1]
        assert _op_name_matches(llm_call.op_name, "claude_agent_sdk.response")
        assert llm_call.output["text"] == expected_text
        assert llm_call.parent_id == root.id


@pytest.mark.asyncio
async def test_conversation_with_result_message_usage(client: WeaveClient) -> None:
    """Verify token usage propagation from ResultMessage."""
    usage = {
        "input_tokens": 500,
        "output_tokens": 200,
        "cache_creation_input_tokens": 50,
        "cache_read_input_tokens": 100,
    }
    messages = [
        _make_assistant_message([_make_text_block("Response text")]),
        _make_result_message(
            usage=usage,
            total_cost_usd=0.025,
            duration_ms=5000,
            num_turns=1,
        ),
    ]

    await _run_conversation(messages)

    calls = list(client.get_calls())
    root = calls[0]
    assert root.output["usage"] == usage
    assert root.output["total_cost_usd"] == 0.025
    assert root.output["duration_ms"] == 5000


@pytest.mark.asyncio
async def test_conversation_with_error(client: WeaveClient) -> None:
    """ResultMessage with is_error=True."""
    messages = [
        _make_result_message(is_error=True, result="Rate limit exceeded"),
    ]

    await _run_conversation(messages)

    calls = list(client.get_calls())
    assert len(calls) == 1

    root = calls[0]
    assert root.output["status"] == "error"
    assert root.exception is not None


@pytest.mark.asyncio
async def test_empty_conversation(client: WeaveClient) -> None:
    """No messages yields no calls."""
    await _run_conversation([])

    calls = list(client.get_calls())
    assert len(calls) == 0


@pytest.mark.asyncio
async def test_call_hierarchy(client: WeaveClient) -> None:
    """Verify parent-child relationships between calls."""
    messages = [
        _make_assistant_message([
            _make_tool_use_block("t1", "search", {"q": "test"}),
        ]),
        _make_assistant_message([
            _make_tool_result_block("t1", content="found it"),
        ]),
        _make_assistant_message([_make_text_block("Here's what I found.")]),
        _make_result_message(),
    ]

    await _run_conversation(messages)

    calls = list(client.get_calls())
    root = calls[0]

    # Root has no parent
    assert root.parent_id is None

    # All children point to root
    for child_call in calls[1:]:
        assert child_call.parent_id == root.id


@pytest.mark.asyncio
async def test_op_names(client: WeaveClient) -> None:
    """Verify correct op names on each call type."""
    messages = [
        _make_assistant_message([
            _make_tool_use_block("t1", "calculator", {"expr": "2+2"}),
        ]),
        _make_assistant_message([
            _make_tool_result_block("t1", content="4"),
        ]),
        _make_assistant_message([_make_text_block("The answer is 4.")]),
        _make_result_message(),
    ]

    await _run_conversation(messages)

    calls = list(client.get_calls())
    assert len(calls) == 3

    root = calls[0]
    assert _op_name_matches(root.op_name, "claude_agent_sdk.ClaudeSDKClient.conversation")

    tool_call = calls[1]
    assert _op_name_matches(tool_call.op_name, "claude_agent_sdk.tool_use.calculator")

    llm_call = calls[2]
    assert _op_name_matches(llm_call.op_name, "claude_agent_sdk.response")


@pytest.mark.asyncio
async def test_transparent_message_yielding(client: WeaveClient) -> None:
    """Verify wrapped receive_response yields messages unchanged."""
    original_messages = [
        _make_assistant_message([_make_text_block("Hello!")]),
        _make_result_message(),
    ]

    received = await _run_conversation(original_messages)

    # The messages yielded to the caller should be identical
    assert len(received) == len(original_messages)
    for orig, recv in zip(original_messages, received, strict=True):
        assert orig is recv


@pytest.mark.asyncio
async def test_tool_result_with_error(client: WeaveClient) -> None:
    """Verify tool calls with is_error=True in tool result."""
    messages = [
        _make_assistant_message([
            _make_tool_use_block("t1", "risky_op", {"x": 1}),
        ]),
        _make_assistant_message([
            _make_tool_result_block("t1", content="Permission denied", is_error=True),
        ]),
        _make_assistant_message([_make_text_block("The operation failed.")]),
        _make_result_message(),
    ]

    await _run_conversation(messages)

    calls = list(client.get_calls())
    tool_call = calls[1]
    assert _op_name_matches(tool_call.op_name, "claude_agent_sdk.tool_use.risky_op")
    assert tool_call.output["content"] == "Permission denied"
    assert tool_call.output["is_error"] is True
