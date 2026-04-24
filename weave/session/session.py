"""Weave Session SDK — structured logging for agent conversations.

Provides Python classes and functions for logging agent conversations
to Weave's Agents tab. All data flows through OpenTelemetry — the SDK
creates OTel spans with GenAI semantic convention attributes.

OTel span emission is not yet implemented — classes are functional
stubs that track state locally.
"""

from __future__ import annotations

import types
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from typing_extensions import Self

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """A single message in a conversation."""

    role: Literal["user", "assistant", "system", "tool"]
    content: str = ""
    tool_call_id: str = ""
    tool_name: str = ""


class Usage(BaseModel):
    """Token usage for an LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


class Reasoning(BaseModel):
    """Reasoning/chain-of-thought content from an LLM call."""

    content: str = ""


class LogResult(BaseModel):
    """Result of a batch log_* call."""

    session_id: str = ""
    trace_ids: list[str] = Field(default_factory=list)
    root_span_ids: list[str] = Field(default_factory=list)
    span_count: int = 0


# ---------------------------------------------------------------------------
# Core span classes
# ---------------------------------------------------------------------------


class _SpanBase(BaseModel):
    """Shared config for span classes that use ``model`` as a field name."""

    model_config = ConfigDict(protected_namespaces=())


class Tool(_SpanBase):
    """One tool execution. Maps to an execute_tool OTel span."""

    name: str = ""
    arguments: str = ""
    result: str = ""
    tool_call_id: str = ""
    duration_ms: int = 0

    _started_at: datetime | None = PrivateAttr(default=None)
    _ended: bool = PrivateAttr(default=False)

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        if self._started_at is not None:
            elapsed = datetime.now(timezone.utc) - self._started_at
            self.duration_ms = int(elapsed.total_seconds() * 1000)

    def __enter__(self) -> Self:
        self._started_at = datetime.now(timezone.utc)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        self.end()
        return False


class LLM(_SpanBase):
    """One LLM API call. Maps to a chat OTel span."""

    model: str = ""
    provider_name: str = ""
    response_id: str = ""
    system_instructions: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    reasoning: Reasoning = Field(default_factory=Reasoning)
    finish_reasons: list[str] = Field(default_factory=list)
    input_messages: list[Message] = Field(default_factory=list)
    output_messages: list[Message] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _ended: bool = PrivateAttr(default=False)
    _token: Token[LLM | None] | None = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)

    def output(self, content: str) -> LLM:
        """Append an assistant message to output_messages."""
        self.output_messages.append(Message(role="assistant", content=content))
        return self

    def think(self, content: str) -> LLM:
        """Set reasoning/chain-of-thought content."""
        self.reasoning = Reasoning(content=content)
        return self

    def attach_file(self, file_id: str) -> LLM:
        """Attach a file reference. Stub — stores nothing yet."""
        return self

    def attach_image(
        self, content: bytes | str, *, mime_type: str = "image/png"
    ) -> LLM:
        """Attach an image. Stub — stores nothing yet."""
        return self

    def attach_uri(self, uri: str, *, modality: str = "image") -> LLM:
        """Attach a URI reference. Stub — stores nothing yet."""
        return self

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        self.ended_at = datetime.now(timezone.utc)
        if self._token is not None:
            _current_llm.reset(self._token)
            self._token = None

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_llm.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        self.end()
        return False


class SubAgent(_SpanBase):
    """A delegated agent invocation within a turn.

    Maps to a nested invoke_agent OTel span in the same trace.
    """

    name: str = ""
    model: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _ended: bool = PrivateAttr(default=False)

    def llm(
        self,
        *,
        model: str = "",
        provider_name: str = "",
        system_instructions: list[str] | None = None,
    ) -> LLM:
        """Start an LLM call within this sub-agent.

        Sets the ``_current_llm`` contextvar so the LLM is visible via
        ``get_current_llm()`` regardless of whether a context manager is used.
        """
        llm = LLM(
            model=model or self.model,
            provider_name=provider_name,
            system_instructions=system_instructions or [],
        )
        llm._token = _current_llm.set(llm)
        return llm

    def tool(self, *, name: str, arguments: str = "", tool_call_id: str = "") -> Tool:
        """Start a tool execution within this sub-agent."""
        return Tool(name=name, arguments=arguments, tool_call_id=tool_call_id)

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        self.ended_at = datetime.now(timezone.utc)

    def __enter__(self) -> Self:
        self.started_at = datetime.now(timezone.utc)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        self.end()
        return False


# ---------------------------------------------------------------------------
# Turn and Session
# ---------------------------------------------------------------------------


class Turn(_SpanBase):
    """One user-agent exchange. Maps to an invoke_agent OTel span (root, new trace)."""

    agent_name: str = ""
    model: str = ""
    messages: list[Message] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _ended: bool = PrivateAttr(default=False)
    _token: Token[Turn | None] | None = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)

    def user(self, content: str) -> Turn:
        """Append a user message mid-turn."""
        self.messages.append(Message(role="user", content=content))
        return self

    def llm(
        self,
        *,
        model: str = "",
        provider_name: str = "",
        system_instructions: list[str] | None = None,
    ) -> LLM:
        """Start an LLM call (chat span, child of this turn).

        Sets the ``_current_llm`` contextvar so the LLM is visible via
        ``get_current_llm()`` regardless of whether a context manager is used.
        """
        llm = LLM(
            model=model or self.model,
            provider_name=provider_name,
            system_instructions=system_instructions or [],
        )
        llm._token = _current_llm.set(llm)
        return llm

    def tool(self, *, name: str, arguments: str = "", tool_call_id: str = "") -> Tool:
        """Start a tool execution (execute_tool span, child of this turn)."""
        return Tool(name=name, arguments=arguments, tool_call_id=tool_call_id)

    def subagent(self, *, name: str, model: str = "") -> SubAgent:
        """Start a sub-agent invocation (nested invoke_agent span, same trace)."""
        return SubAgent(name=name, model=model or self.model)

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        self.ended_at = datetime.now(timezone.utc)
        if self._token is not None:
            _current_turn.reset(self._token)
            self._token = None

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_turn.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        self.end()
        return False


class Session(_SpanBase):
    """A conversation session. Groups turns by conversation_id (no span)."""

    session_id: str = ""
    session_name: str = ""
    agent_name: str = ""
    model: str = ""
    include_content: bool = True

    _ended: bool = PrivateAttr(default=False)
    _token: Token[Session | None] | None = PrivateAttr(default=None)
    _current_turn: Turn | None = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        if not self.session_id:
            self.session_id = str(uuid.uuid4())

    def start_turn(
        self,
        *,
        user_message: str = "",
        model: str = "",
        agent_name: str = "",
    ) -> Turn:
        """Create a new turn. Auto-ends the previous turn if still open.

        Sets the ``_current_turn`` contextvar so the turn is visible via
        ``get_current_turn()`` regardless of whether a context manager is used.
        """
        if self._current_turn is not None and not self._current_turn._ended:
            self._current_turn.end()
        turn = Turn(
            agent_name=agent_name or self.agent_name,
            model=model or self.model,
        )
        if user_message:
            turn.messages.append(Message(role="user", content=user_message))
        turn._token = _current_turn.set(turn)
        self._current_turn = turn
        return turn

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        if self._current_turn is not None and not self._current_turn._ended:
            self._current_turn.end()
        if self._token is not None:
            _current_session.reset(self._token)
            self._token = None

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_session.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        self.end()
        return False


# ---------------------------------------------------------------------------
# Contextvars
# ---------------------------------------------------------------------------

_current_session: ContextVar[Session | None] = ContextVar(
    "_current_session", default=None
)
_current_turn: ContextVar[Turn | None] = ContextVar("_current_turn", default=None)
_current_llm: ContextVar[LLM | None] = ContextVar("_current_llm", default=None)


# ---------------------------------------------------------------------------
# Top-level functions
# ---------------------------------------------------------------------------


def start_session(
    *,
    agent_name: str = "",
    model: str = "",
    session_id: str = "",
    session_name: str = "",
    include_content: bool = True,
) -> Session:
    """Create and activate a session. Sets the contextvar for cross-module access."""
    session = Session(
        agent_name=agent_name,
        model=model,
        session_id=session_id,
        session_name=session_name,
        include_content=include_content,
    )
    session._token = _current_session.set(session)
    return session


def start_turn(
    *,
    user_message: str = "",
    model: str = "",
    agent_name: str = "",
) -> Turn:
    """Create and activate a turn. Uses the current session if available.

    If no session is active, returns a disconnected Turn (no contextvar set).
    """
    session = get_current_session()
    if session is not None:
        return session.start_turn(
            user_message=user_message, model=model, agent_name=agent_name
        )
    turn = Turn(agent_name=agent_name, model=model)
    if user_message:
        turn.messages.append(Message(role="user", content=user_message))
    return turn


def start_llm(
    *,
    model: str = "",
    provider_name: str = "",
    system_instructions: list[str] | None = None,
) -> LLM:
    """Create and activate an LLM call. Uses the current turn if available.

    If no turn is active, returns a disconnected LLM (no contextvar set).
    """
    turn = get_current_turn()
    if turn is not None:
        return turn.llm(
            model=model,
            provider_name=provider_name,
            system_instructions=system_instructions,
        )
    return LLM(
        model=model,
        provider_name=provider_name,
        system_instructions=system_instructions or [],
    )


def end_session() -> None:
    """End the current session (from contextvar)."""
    session = get_current_session()
    if session is not None:
        session.end()


def end_turn() -> None:
    """End the current turn (from contextvar)."""
    turn = get_current_turn()
    if turn is not None:
        turn.end()


def end_llm() -> None:
    """End the current LLM call (from contextvar)."""
    llm = get_current_llm()
    if llm is not None:
        llm.end()


def get_current_session() -> Session | None:
    """Return the active session from contextvar, or None."""
    return _current_session.get()


def get_current_turn() -> Turn | None:
    """Return the active turn from contextvar, or None."""
    return _current_turn.get()


def get_current_llm() -> LLM | None:
    """Return the active LLM call from contextvar, or None."""
    return _current_llm.get()


def log_turn(
    *,
    session_id: str,
    messages: list[dict[str, str]] | None = None,
    spans: list[LLM | Tool] | None = None,
    agent_name: str = "",
    model: str = "",
    session_name: str = "",
) -> LogResult:
    """Batch-ingest a single turn. Stub — returns empty LogResult."""
    return LogResult(session_id=session_id)


def log_session(
    *,
    turns: list[dict[str, Any]],
    agent_name: str = "",
    model: str = "",
    session_id: str = "",
    session_name: str = "",
) -> LogResult:
    """Batch-ingest a complete session. Stub — returns empty LogResult."""
    return LogResult(session_id=session_id or str(uuid.uuid4()))
