"""Weave Session SDK — structured logging for agent conversations.

Provides Python classes and functions for logging agent conversations
to Weave's Agents tab. All data flows through OpenTelemetry — the SDK
creates OTel spans with GenAI semantic convention attributes.

Each SDK class creates OTel spans with GenAI semantic convention
attributes when used as context managers.
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


class MediaAttachment(BaseModel):
    """A media attachment on an LLM call."""

    kind: Literal["blob", "uri", "file"]
    modality: str = ""
    mime_type: str = ""
    content: bytes | str = ""
    uri: str = ""
    file_id: str = ""


class LogResult(BaseModel):
    """Result of a batch log_* call."""

    session_id: str = ""
    trace_ids: list[str] = Field(default_factory=list)
    root_span_ids: list[str] = Field(default_factory=list)
    span_count: int = 0


# ---------------------------------------------------------------------------
# Core span classes
# ---------------------------------------------------------------------------


def _try_import_otel() -> tuple[Any, Any, Any] | None:
    """Try to import opentelemetry modules. Returns (trace, context, otel_setup) or None."""
    try:
        from opentelemetry import context as otel_context
        from opentelemetry import trace

        from weave.session import otel_setup
    except ImportError:
        return None
    else:
        return trace, otel_context, otel_setup


class _SpanBase(BaseModel):
    """Shared config for span classes that use ``model`` as a field name."""

    model_config = ConfigDict(protected_namespaces=())

    _otel_span: Any = PrivateAttr(default=None)  # trace.Span
    _otel_token: Any = PrivateAttr(default=None)  # context token from attach()

    def _start_otel_span(self, name: str, *, new_trace: bool = False) -> None:
        """Create an OTel span and attach it to the current context."""
        otel = _try_import_otel()
        if otel is None:
            return
        trace, otel_context, otel_setup = otel
        tracer = otel_setup.get_tracer()
        if new_trace:
            from opentelemetry.context import Context

            self._otel_span = tracer.start_span(name, context=Context())
        else:
            self._otel_span = tracer.start_span(name)
        self._otel_token = otel_context.attach(
            trace.set_span_in_context(self._otel_span)
        )

    def _end_otel_span(self, attrs: dict[str, Any]) -> None:
        """Set attributes and end the OTel span, then detach context."""
        if self._otel_span is not None and self._otel_span.is_recording():
            for k, v in attrs.items():
                self._otel_span.set_attribute(k, v)
            self._otel_span.end()

        if self._otel_token is not None:
            otel = _try_import_otel()
            if otel is not None:
                _, otel_context, _ = otel
                otel_context.detach(self._otel_token)
            self._otel_token = None

    def _record_otel_error(self, exc_val: BaseException) -> None:
        """Record an exception on the OTel span."""
        if self._otel_span is None:
            return
        try:
            from opentelemetry.trace import StatusCode

            self._otel_span.set_status(StatusCode.ERROR, str(exc_val))
            self._otel_span.record_exception(exc_val)
        except ImportError:
            pass


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

        from weave.session.session_otel import execute_tool_attributes

        session = _current_session.get()
        include = session.include_content if session else True
        attrs = execute_tool_attributes(
            tool_name=self.name,
            conversation_id=session.session_id if session else "",
            tool_call_arguments=self.arguments if include else "",
            tool_call_result=self.result if include else "",
            tool_call_id=self.tool_call_id,
        )
        self._end_otel_span(attrs)

    def __enter__(self) -> Self:
        self._started_at = datetime.now(timezone.utc)
        self._start_otel_span(f"execute_tool {self.name}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        if exc_type is not None:
            self._record_otel_error(exc_val)  # type: ignore[arg-type]
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
    media_attachments: list[MediaAttachment] = Field(default_factory=list)
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

    def attach_media(
        self,
        *,
        content: bytes | str = "",
        uri: str = "",
        file_id: str = "",
        mime_type: str = "",
        modality: str = "",
    ) -> LLM:
        """Attach media to this LLM call.

        Exactly one of content, uri, or file_id must be provided.
        Modality is inferred from mime_type when not set explicitly.
        """
        sources = sum(bool(s) for s in (content, uri, file_id))
        if sources != 1:
            raise ValueError("Exactly one of content, uri, or file_id must be provided")

        if not modality and mime_type:
            prefix = mime_type.split("/", maxsplit=1)[0]
            if prefix in {"image", "audio", "video"}:
                modality = prefix

        if content:
            kind: Literal["blob", "uri", "file"] = "blob"
        elif uri:
            kind = "uri"
        else:
            kind = "file"

        self.media_attachments.append(
            MediaAttachment(
                kind=kind,
                modality=modality or "unknown",
                mime_type=mime_type,
                content=content,
                uri=uri,
                file_id=file_id,
            )
        )
        return self

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        self.ended_at = datetime.now(timezone.utc)

        from weave.session.session_otel import llm_attributes

        session = _current_session.get()
        include = session.include_content if session else True
        attrs = llm_attributes(
            model=self.model,
            provider_name=self.provider_name,
            conversation_id=session.session_id if session else "",
            input_messages=self.input_messages if include else None,
            output_messages=self.output_messages if include else None,
            system_instructions=self.system_instructions if include else None,
            usage=self.usage,
            reasoning=self.reasoning,
            finish_reasons=self.finish_reasons,
            response_id=self.response_id,
        )
        self._end_otel_span(attrs)

        if self._token is not None:
            _current_llm.reset(self._token)
            self._token = None

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_llm.set(self)
        self._start_otel_span(f"chat {self.model}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        if exc_type is not None:
            self._record_otel_error(exc_val)  # type: ignore[arg-type]
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

        from weave.session.session_otel import invoke_agent_attributes

        session = _current_session.get()
        attrs = invoke_agent_attributes(
            agent_name=self.name,
            model=self.model,
            conversation_id=session.session_id if session else "",
            conversation_name=session.session_name if session else "",
        )
        self._end_otel_span(attrs)

    def __enter__(self) -> Self:
        self.started_at = datetime.now(timezone.utc)
        self._start_otel_span(f"invoke_agent {self.name}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        if exc_type is not None:
            self._record_otel_error(exc_val)  # type: ignore[arg-type]
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
    _session: Any = PrivateAttr(default=None)  # Session reference

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

        from weave.session.session_otel import invoke_agent_attributes

        include = self._session.include_content if self._session else True
        attrs = invoke_agent_attributes(
            agent_name=self.agent_name,
            conversation_id=self._session.session_id if self._session else "",
            conversation_name=self._session.session_name if self._session else "",
            model=self.model,
            input_messages=self.messages if include else None,
        )
        self._end_otel_span(attrs)

        if self._token is not None:
            _current_turn.reset(self._token)
            self._token = None

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_turn.set(self)
        self._start_otel_span(f"invoke_agent {self.agent_name}", new_trace=True)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        if exc_type is not None:
            self._record_otel_error(exc_val)  # type: ignore[arg-type]
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
        user_message: str | None = "",
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
        turn._session = self
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
    user_message: str | None = "",
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


def start_tool(
    *,
    name: str,
    arguments: str = "",
    tool_call_id: str = "",
) -> Tool:
    """Create a tool execution span. Uses the current turn if available.

    If no turn is active, returns a standalone Tool.
    """
    return Tool(name=name, arguments=arguments, tool_call_id=tool_call_id)


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
