"""Tests for the Claude Agent SDK Weave integration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import weave.integrations.claude_agent_sdk.claude_agent_sdk as _integration_mod
from weave.integrations.claude_agent_sdk.claude_agent_sdk import (
    ClaudeAgentSDKPatcher,
    TracingAsyncIterator,
    _active_tool_calls,
    _extract_inputs,
    _extract_output,
    _merge_hooks,
    _post_tool_use_hook,
    _pre_tool_use_hook,
    get_claude_agent_sdk_patcher,
)
from weave.integrations.patcher import NoOpPatcher
from weave.trace.autopatch import IntegrationSettings

# ---------------------------------------------------------------------------
# Lightweight stubs for the SDK types, so we can test without launching Claude
# ---------------------------------------------------------------------------


@dataclass
class FakeTextBlock:
    text: str


@dataclass
class FakeThinkingBlock:
    text: str


@dataclass
class FakeToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class FakeAssistantMessage:
    content: list[Any]
    model: str = "claude-sonnet-4-20250514"
    parent_tool_use_id: str | None = None
    error: str | None = None


@dataclass
class FakeResultMessage:
    subtype: str = "result"
    duration_ms: int = 1200
    duration_api_ms: int = 1000
    is_error: bool = False
    num_turns: int = 2
    session_id: str = "test-session"
    total_cost_usd: float | None = 0.005
    usage: dict[str, Any] | None = None
    result: str | None = "The answer is 4."
    structured_output: Any = None


@dataclass
class FakeClaudeAgentOptions:
    tools: Any = None
    allowed_tools: list[str] | None = None
    system_prompt: str | None = None
    mcp_servers: Any = None
    permission_mode: str | None = None
    continue_conversation: bool = False
    resume: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    disallowed_tools: list[str] | None = None
    model: str | None = None
    fallback_model: str | None = None
    betas: list[str] | None = None
    permission_prompt_tool_name: str | None = None
    cwd: str | None = None
    cli_path: str | None = None
    settings: str | None = None
    add_dirs: list[str] | None = None
    env: dict[str, str] | None = None
    extra_args: dict[str, str | None] | None = None
    max_buffer_size: int | None = None
    debug_stderr: Any = None
    stderr: Any = None
    can_use_tool: Any = None
    hooks: dict[str, list[Any]] | None = None
    user: str | None = None
    include_partial_messages: bool = False
    fork_session: bool = False
    agents: Any = None
    setting_sources: Any = None
    sandbox: Any = None
    plugins: list[Any] | None = None
    max_thinking_tokens: int | None = None
    thinking: Any = None
    effort: str | None = None
    output_format: Any = None
    enable_file_checkpointing: bool = False

    def __post_init__(self) -> None:
        if self.allowed_tools is None:
            self.allowed_tools = []
        if self.betas is None:
            self.betas = []
        if self.add_dirs is None:
            self.add_dirs = []
        if self.env is None:
            self.env = {}
        if self.extra_args is None:
            self.extra_args = {}
        if self.plugins is None:
            self.plugins = []
        if self.mcp_servers is None:
            self.mcp_servers = {}
        if self.disallowed_tools is None:
            self.disallowed_tools = []


@dataclass
class FakeHookMatcher:
    matcher: str | None = None
    hooks: list[Any] | None = None
    timeout: float | None = None

    def __post_init__(self) -> None:
        if self.hooks is None:
            self.hooks = []


# ---------------------------------------------------------------------------
# Helper: build a simple async iterator from a list of messages
# ---------------------------------------------------------------------------


async def _aiter_messages(messages: list[Any]) -> AsyncIterator[Any]:
    for msg in messages:
        yield msg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_active_tool_calls() -> Generator[None, None, None]:
    """Ensure tool call tracking state is clean between tests."""
    _active_tool_calls.clear()
    _integration_mod._current_parent_call = None
    yield
    _active_tool_calls.clear()
    _integration_mod._current_parent_call = None


@pytest.fixture
def mock_sdk() -> Generator[MagicMock, None, None]:
    """Patch the claude_agent_sdk module with our fakes."""
    mock = MagicMock()
    mock.AssistantMessage = FakeAssistantMessage
    mock.ResultMessage = FakeResultMessage
    mock.TextBlock = FakeTextBlock
    mock.ThinkingBlock = FakeThinkingBlock
    mock.ToolUseBlock = FakeToolUseBlock
    mock.ClaudeAgentOptions = FakeClaudeAgentOptions
    mock.HookMatcher = FakeHookMatcher
    with patch.dict("sys.modules", {"claude_agent_sdk": mock}):
        yield mock


# ---------------------------------------------------------------------------
# Tests for helper functions
# ---------------------------------------------------------------------------


class TestExtractInputs:
    def test_string_prompt(self) -> None:
        inputs = _extract_inputs("Hello", None)
        assert inputs == {"prompt": "Hello"}

    def test_async_iterable_prompt(self) -> None:
        inputs = _extract_inputs(_aiter_messages([]), None)
        assert inputs["prompt"] == "<async_iterable>"

    def test_with_options(self) -> None:
        opts = FakeClaudeAgentOptions(
            model="claude-sonnet-4-20250514",
            system_prompt="Be helpful",
            max_turns=5,
            permission_mode="acceptEdits",
        )
        inputs = _extract_inputs("Hello", opts)
        assert inputs["prompt"] == "Hello"
        assert inputs["model"] == "claude-sonnet-4-20250514"
        assert inputs["system_prompt"] == "Be helpful"
        assert inputs["max_turns"] == 5
        assert inputs["permission_mode"] == "acceptEdits"

    def test_none_options_fields_excluded(self) -> None:
        opts = FakeClaudeAgentOptions()
        inputs = _extract_inputs("Hello", opts)
        assert "model" not in inputs
        assert "system_prompt" not in inputs
        assert "max_turns" not in inputs


class TestExtractOutput:
    def test_basic_result(self) -> None:
        result = FakeResultMessage(
            result="42",
            num_turns=3,
            duration_ms=500,
            total_cost_usd=0.01,
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        output = _extract_output(result, "accumulated text")
        assert output["result"] == "42"
        assert output["text"] == "accumulated text"
        assert output["num_turns"] == 3
        assert output["duration_ms"] == 500
        assert output["total_cost_usd"] == 0.01
        assert output["usage"] == {"input_tokens": 100, "output_tokens": 50}

    def test_no_cost(self) -> None:
        result = FakeResultMessage(total_cost_usd=None)
        output = _extract_output(result, "")
        assert "total_cost_usd" not in output

    def test_no_usage(self) -> None:
        result = FakeResultMessage(usage=None)
        output = _extract_output(result, "")
        assert "usage" not in output


class TestMergeHooks:
    def test_no_existing_hooks(self, mock_sdk: MagicMock) -> None:
        hooks = _merge_hooks(None)
        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks
        assert len(hooks["PreToolUse"]) == 1
        assert len(hooks["PostToolUse"]) == 1

    def test_preserves_existing_hooks(self, mock_sdk: MagicMock) -> None:
        user_hook = FakeHookMatcher(matcher="Bash", hooks=[lambda *a: {}])
        existing = {"PreToolUse": [user_hook]}
        hooks = _merge_hooks(existing)
        # User hook preserved + our hook added
        assert len(hooks["PreToolUse"]) == 2
        assert hooks["PreToolUse"][0] is user_hook
        # PostToolUse added
        assert len(hooks["PostToolUse"]) == 1

    def test_preserves_other_hook_types(self, mock_sdk: MagicMock) -> None:
        stop_hook = FakeHookMatcher(hooks=[lambda *a: {}])
        existing = {"Stop": [stop_hook]}
        hooks = _merge_hooks(existing)
        assert "Stop" in hooks
        assert hooks["Stop"][0] is stop_hook


# ---------------------------------------------------------------------------
# Tests for hooks
# ---------------------------------------------------------------------------


class TestPreToolUseHook:
    def test_creates_child_call(self, mock_sdk: MagicMock) -> None:
        mock_wc = MagicMock()
        mock_call = MagicMock()
        mock_wc.create_call.return_value = mock_call
        mock_parent = MagicMock()

        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_use_id": "tu_123",
            "session_id": "s1",
            "transcript_path": "/tmp/t",
            "cwd": "/home",
            "hook_event_name": "PreToolUse",
        }

        _integration_mod._current_parent_call = mock_parent
        with patch(
            "weave.integrations.claude_agent_sdk.claude_agent_sdk.get_weave_client",
            return_value=mock_wc,
        ):
            result = asyncio.get_event_loop().run_until_complete(
                _pre_tool_use_hook(hook_input, None, None)
            )

        assert result == {}
        mock_wc.create_call.assert_called_once()
        call_kwargs = mock_wc.create_call.call_args
        assert call_kwargs.kwargs["op"] == "claude_agent_sdk.tool_use"
        assert call_kwargs.kwargs["inputs"]["tool_name"] == "Bash"
        assert call_kwargs.kwargs["display_name"] == "Bash"
        assert call_kwargs.kwargs["parent"] is mock_parent
        assert "tu_123" in _active_tool_calls

    def test_noop_without_client(self) -> None:
        with patch(
            "weave.integrations.claude_agent_sdk.claude_agent_sdk.get_weave_client",
            return_value=None,
        ):
            result = asyncio.get_event_loop().run_until_complete(
                _pre_tool_use_hook(
                    {"tool_name": "Bash", "tool_input": {}, "tool_use_id": "tu_1"},
                    None,
                    None,
                )
            )
        assert result == {}
        assert len(_active_tool_calls) == 0


class TestPostToolUseHook:
    def test_finishes_child_call(self, mock_sdk: MagicMock) -> None:
        mock_wc = MagicMock()
        mock_call = MagicMock()
        _active_tool_calls["tu_456"] = mock_call

        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_response": "file1.txt\nfile2.txt",
            "tool_use_id": "tu_456",
            "session_id": "s1",
            "transcript_path": "/tmp/t",
            "cwd": "/home",
            "hook_event_name": "PostToolUse",
        }

        with patch(
            "weave.integrations.claude_agent_sdk.claude_agent_sdk.get_weave_client",
            return_value=mock_wc,
        ):
            result = asyncio.get_event_loop().run_until_complete(
                _post_tool_use_hook(hook_input, None, None)
            )

        assert result == {}
        mock_wc.finish_call.assert_called_once_with(
            mock_call,
            output={"tool_response": "file1.txt\nfile2.txt"},
        )
        assert "tu_456" not in _active_tool_calls

    def test_noop_for_unknown_tool_use_id(self, mock_sdk: MagicMock) -> None:
        mock_wc = MagicMock()
        with patch(
            "weave.integrations.claude_agent_sdk.claude_agent_sdk.get_weave_client",
            return_value=mock_wc,
        ):
            result = asyncio.get_event_loop().run_until_complete(
                _post_tool_use_hook(
                    {"tool_use_id": "unknown", "tool_response": "ok"},
                    None,
                    None,
                )
            )
        assert result == {}
        mock_wc.finish_call.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for TracingAsyncIterator
# ---------------------------------------------------------------------------


class TestTracingAsyncIterator:
    def test_creates_parent_call_and_finishes_on_result(
        self, mock_sdk: MagicMock
    ) -> None:
        mock_wc = MagicMock()
        mock_parent_call = MagicMock()
        mock_wc.create_call.return_value = mock_parent_call

        messages = [
            FakeAssistantMessage(content=[FakeTextBlock(text="Hello ")]),
            FakeAssistantMessage(content=[FakeTextBlock(text="world")]),
            FakeResultMessage(result="Hello world", num_turns=1),
        ]

        async def run() -> list[Any]:
            collected = []
            with patch(
                "weave.integrations.claude_agent_sdk.claude_agent_sdk.get_weave_client",
                return_value=mock_wc,
            ), patch(
                "weave.integrations.claude_agent_sdk.claude_agent_sdk.call_context"
            ):
                iterator = TracingAsyncIterator(
                    _aiter_messages(messages), {"prompt": "test"}
                )
                async for msg in iterator:
                    collected.append(msg)
            return collected

        result = asyncio.get_event_loop().run_until_complete(run())

        assert len(result) == 3
        # 1 parent + 2 assistant turn child calls = 3 create_call
        assert mock_wc.create_call.call_count == 3
        # 2 assistant turn finish + 1 parent finish = 3 finish_call
        assert mock_wc.finish_call.call_count == 3
        # Last finish_call is the parent with accumulated text
        parent_finish = mock_wc.finish_call.call_args_list[-1]
        assert parent_finish.kwargs["output"]["text"] == "Hello world"
        assert parent_finish.kwargs["output"]["result"] == "Hello world"

    def test_creates_thinking_child_call(self, mock_sdk: MagicMock) -> None:
        mock_wc = MagicMock()
        mock_parent_call = MagicMock()
        mock_wc.create_call.return_value = mock_parent_call

        messages = [
            FakeAssistantMessage(
                content=[
                    FakeThinkingBlock(text="Let me think about this..."),
                    FakeTextBlock(text="The answer is 42."),
                ]
            ),
            FakeResultMessage(result="42"),
        ]

        async def run() -> list[Any]:
            collected = []
            with patch(
                "weave.integrations.claude_agent_sdk.claude_agent_sdk.get_weave_client",
                return_value=mock_wc,
            ), patch(
                "weave.integrations.claude_agent_sdk.claude_agent_sdk.call_context"
            ):
                iterator = TracingAsyncIterator(
                    _aiter_messages(messages), {"prompt": "test"}
                )
                async for msg in iterator:
                    collected.append(msg)
            return collected

        asyncio.get_event_loop().run_until_complete(run())

        # 1 parent + 1 thinking + 1 assistant turn = 3 create_call
        assert mock_wc.create_call.call_count == 3
        create_calls = mock_wc.create_call.call_args_list
        # Second call is the thinking child
        assert create_calls[1].kwargs["op"] == "claude_agent_sdk.thinking"
        assert create_calls[1].kwargs["display_name"] == "Thinking"
        # Third call is the assistant turn child
        assert create_calls[2].kwargs["op"] == "claude_agent_sdk.assistant_turn"
        assert create_calls[2].kwargs["display_name"] == "Assistant Turn"

    def test_finishes_with_exception_on_error(self, mock_sdk: MagicMock) -> None:
        mock_wc = MagicMock()
        mock_parent_call = MagicMock()
        mock_wc.create_call.return_value = mock_parent_call

        async def _failing_iter() -> AsyncIterator[Any]:
            yield FakeAssistantMessage(content=[FakeTextBlock(text="Hi")])
            raise RuntimeError("Connection lost")

        async def run() -> None:
            with patch(
                "weave.integrations.claude_agent_sdk.claude_agent_sdk.get_weave_client",
                return_value=mock_wc,
            ), patch(
                "weave.integrations.claude_agent_sdk.claude_agent_sdk.call_context"
            ):
                iterator = TracingAsyncIterator(
                    _failing_iter(), {"prompt": "test"}
                )
                with pytest.raises(RuntimeError, match="Connection lost"):
                    async for _ in iterator:
                        pass

        asyncio.get_event_loop().run_until_complete(run())
        # 1 assistant turn finish + 1 parent finish with exception = 2
        assert mock_wc.finish_call.call_count == 2
        # Last finish_call is the parent with the exception
        parent_finish = mock_wc.finish_call.call_args_list[-1]
        assert parent_finish.kwargs.get("exception") is not None

    def test_no_tracing_without_client(self, mock_sdk: MagicMock) -> None:
        messages = [
            FakeAssistantMessage(content=[FakeTextBlock(text="Hi")]),
            FakeResultMessage(result="Hi"),
        ]

        async def run() -> list[Any]:
            collected = []
            with patch(
                "weave.integrations.claude_agent_sdk.claude_agent_sdk.get_weave_client",
                return_value=None,
            ):
                iterator = TracingAsyncIterator(
                    _aiter_messages(messages), {"prompt": "test"}
                )
                async for msg in iterator:
                    collected.append(msg)
            return collected

        result = asyncio.get_event_loop().run_until_complete(run())
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Tests for patcher
# ---------------------------------------------------------------------------


class TestGetClaudeAgentSdkPatcher:
    def test_disabled_returns_noop(self) -> None:
        settings = IntegrationSettings(enabled=False)
        patcher = get_claude_agent_sdk_patcher(settings)
        assert isinstance(patcher, NoOpPatcher)

    def test_returns_patcher_instance(self) -> None:
        # Reset the module-level singleton
        import weave.integrations.claude_agent_sdk.claude_agent_sdk as mod

        mod._claude_agent_sdk_patcher = None
        patcher = get_claude_agent_sdk_patcher()
        assert isinstance(patcher, ClaudeAgentSDKPatcher)
        # Reset again to avoid leaking state
        mod._claude_agent_sdk_patcher = None

    def test_singleton_behavior(self) -> None:
        import weave.integrations.claude_agent_sdk.claude_agent_sdk as mod

        mod._claude_agent_sdk_patcher = None
        p1 = get_claude_agent_sdk_patcher()
        p2 = get_claude_agent_sdk_patcher()
        assert p1 is p2
        mod._claude_agent_sdk_patcher = None
