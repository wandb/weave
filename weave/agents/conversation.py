"""Imperative conversation logging SDK.

Buffer agent events client-side and flush completed turns to the Weave
trace server.  No OTel dependency — just HTTP POST of structured JSON.

Examples:
    Basic turn-by-turn logging::

        from weave.agents.conversation import conversation

        conv = conversation("session-1", agent_name="my-agent", model="gpt-4o")

        conv.user("What's the weather in Tokyo?")
        conv.assistant("Let me check that for you.")
        conv.tool_call("get_weather", arguments='{"city": "Tokyo"}', result="75°F")
        conv.assistant("It's 75°F in Tokyo right now.")
        conv.flush()

        conv.user("What about Osaka?")
        conv.assistant("72°F in Osaka.")
        conv.flush()

    Auto-flush on turn boundary::

        conv.user("First question")
        conv.assistant("First answer")
        conv.user("Second question")  # auto-flushes the first turn
        conv.assistant("Second answer")
        conv.flush()  # flushes the second turn
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import uuid
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _default_url() -> str:
    return os.environ.get("WF_TRACE_SERVER_URL", "http://localhost:6345").rstrip("/")


def _default_auth() -> tuple[str, str] | None:
    key = os.environ.get("WANDB_API_KEY", "")
    return ("api", key) if key else None


def _default_project() -> str:
    entity = os.environ.get("WANDB_ENTITY", "")
    project = os.environ.get("WANDB_PROJECT", "agents")
    if entity:
        return f"{entity}/{project}"
    return ""


class Conversation:
    """Client-side buffer for logging agent conversations turn by turn.

    Messages accumulate in memory. ``flush()`` converts the buffer to a
    structured turn and POSTs it to ``/genai/conversations/ingest``.

    Args:
        conversation_id: Unique conversation identifier. Generated if empty.
        agent_name: Default agent name for turns.
        model: Default model name for turns.
        project: Project ID (``entity/project``). Inferred from env if empty.
        server_url: Trace server base URL. Defaults to ``WF_TRACE_SERVER_URL``.
        conversation_name: Human-readable name for the conversation.
        auto_flush: If True, calling ``user()`` after agent content
            auto-flushes the previous turn.
    """

    def __init__(
        self,
        conversation_id: str = "",
        *,
        agent_name: str = "",
        model: str = "",
        project: str = "",
        server_url: str = "",
        conversation_name: str = "",
        auto_flush: bool = True,
    ) -> None:
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.conversation_name = conversation_name
        self.agent_name = agent_name
        self.model = model
        self.project = project or _default_project()
        self.server_url = server_url or _default_url()
        self.auto_flush = auto_flush

        self._messages: list[dict[str, str]] = []
        self._tool_calls: list[dict[str, Any]] = []
        self._system_instructions: list[str] = []
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._reasoning_content: str = ""
        self._has_agent_content: bool = False
        self._flushed_turns: int = 0

        atexit.register(self._atexit_flush)

    def user(self, content: str) -> Conversation:
        """Log a user message.

        If ``auto_flush`` is enabled and there's pending agent content,
        this flushes the previous turn first.

        Args:
            content: The user's message text.

        Returns:
            self, for chaining.
        """
        if self.auto_flush and self._has_agent_content:
            self.flush()
        self._messages.append({"role": "user", "content": content})
        return self

    def assistant(self, content: str) -> Conversation:
        """Log an assistant message.

        Args:
            content: The assistant's response text.

        Returns:
            self, for chaining.
        """
        self._messages.append({"role": "assistant", "content": content})
        self._has_agent_content = True
        return self

    def system(self, content: str) -> Conversation:
        """Log a system instruction.

        System instructions are attached to the next flushed turn.

        Args:
            content: The system instruction text.

        Returns:
            self, for chaining.
        """
        self._system_instructions.append(content)
        return self

    def tool_call(
        self,
        tool_name: str,
        *,
        arguments: str | dict = "",
        result: str = "",
        duration_ms: int = 0,
    ) -> Conversation:
        """Log a tool call.

        Args:
            tool_name: Name of the tool invoked.
            arguments: Tool arguments (JSON string or dict).
            result: Tool execution result.
            duration_ms: Tool execution duration in milliseconds.

        Returns:
            self, for chaining.
        """
        args_str = json.dumps(arguments) if isinstance(arguments, dict) else arguments
        self._tool_calls.append({
            "tool_name": tool_name,
            "arguments": args_str,
            "result": result,
            "duration_ms": duration_ms,
        })
        self._has_agent_content = True
        return self

    def metrics(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_content: str = "",
    ) -> Conversation:
        """Attach token metrics to the current turn.

        Args:
            input_tokens: Number of input tokens for this turn.
            output_tokens: Number of output tokens for this turn.
            reasoning_content: Reasoning/chain-of-thought text.

        Returns:
            self, for chaining.
        """
        self._input_tokens += input_tokens
        self._output_tokens += output_tokens
        if reasoning_content:
            self._reasoning_content = reasoning_content
        return self

    def flush(self) -> dict[str, Any] | None:
        """Flush the buffered turn to the server.

        Converts accumulated messages, tool calls, and metrics into a
        ``GenAIStructuredTurn`` and POSTs to ``/genai/conversations/ingest``.

        Returns:
            The server response dict, or None if there was nothing to flush.
        """
        if not self._messages and not self._tool_calls:
            return None

        turn = {
            "messages": self._messages,
            "tool_calls": self._tool_calls,
            "agent_name": self.agent_name,
            "model": self.model,
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "reasoning_content": self._reasoning_content,
            "system_instructions": self._system_instructions,
        }

        payload = {
            "conversation_id": self.conversation_id,
            "conversation_name": self.conversation_name,
            "agent_name": self.agent_name,
            "turns": [turn],
        }

        self._reset_buffer()

        url = f"{self.server_url}/genai/conversations/ingest"
        params = {"project_id": self.project} if self.project else {}
        auth = _default_auth()

        try:
            r = requests.post(url, json=payload, params=params, auth=auth, timeout=30)
            if r.status_code != 200:
                logger.error("Failed to flush turn: %s %s", r.status_code, r.text[:200])
                return None
            result = r.json()
            self._flushed_turns += 1
            logger.debug(
                "Flushed turn %d: conv=%s spans=%s",
                self._flushed_turns,
                result.get("conversation_id", "?"),
                result.get("span_count", "?"),
            )
            return result
        except Exception:
            logger.error("Failed to flush turn", exc_info=True)
            return None

    def export_atif(self) -> dict[str, Any] | None:
        """Export the conversation as an ATIF trajectory from the server.

        Returns:
            The ATIF trajectory dict, or None on error.
        """
        url = f"{self.server_url}/genai/conversations/export/atif"
        params = {"project_id": self.project} if self.project else {}
        payload = {
            "project_id": self.project,
            "conversation_id": self.conversation_id,
        }
        auth = _default_auth()

        try:
            r = requests.post(url, json=payload, auth=auth, params=params, timeout=30)
            if r.status_code != 200:
                logger.error("Failed to export ATIF: %s %s", r.status_code, r.text[:200])
                return None
            return r.json()
        except Exception:
            logger.error("Failed to export ATIF", exc_info=True)
            return None

    @property
    def turns_flushed(self) -> int:
        """Number of turns successfully flushed so far."""
        return self._flushed_turns

    @property
    def pending(self) -> bool:
        """Whether there are unflushed messages or tool calls."""
        return bool(self._messages or self._tool_calls)

    def _reset_buffer(self) -> None:
        self._messages = []
        self._tool_calls = []
        self._system_instructions = []
        self._input_tokens = 0
        self._output_tokens = 0
        self._reasoning_content = ""
        self._has_agent_content = False

    def _atexit_flush(self) -> None:
        if self.pending:
            logger.debug("Auto-flushing pending turn on exit")
            self.flush()

    def __repr__(self) -> str:
        return (
            f"Conversation(id={self.conversation_id!r}, "
            f"agent={self.agent_name!r}, "
            f"turns_flushed={self._flushed_turns}, "
            f"pending={self.pending})"
        )


def conversation(
    conversation_id: str = "",
    *,
    agent_name: str = "",
    model: str = "",
    project: str = "",
    server_url: str = "",
    conversation_name: str = "",
    auto_flush: bool = True,
) -> Conversation:
    """Create a conversation logger.

    Args:
        conversation_id: Unique ID for the conversation. Generated if empty.
        agent_name: Default agent name.
        model: Default model name.
        project: Project ID (``entity/project``). Inferred from env if empty.
        server_url: Trace server URL. Defaults to ``WF_TRACE_SERVER_URL``.
        conversation_name: Human-readable conversation name.
        auto_flush: Auto-flush when a new ``user()`` call follows agent content.

    Returns:
        A ``Conversation`` instance.

    Examples:
        >>> conv = conversation("session-1", agent_name="bot", model="gpt-4o")
        >>> conv.user("Hello").assistant("Hi there!").flush()
    """
    return Conversation(
        conversation_id,
        agent_name=agent_name,
        model=model,
        project=project,
        server_url=server_url,
        conversation_name=conversation_name,
        auto_flush=auto_flush,
    )
