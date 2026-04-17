"""Session / Turn / Step / Tool logging API.

Three usage patterns from a single implementation:

1. Context manager::

    with weave.start_session(agent_name="bot") as session:
        with session.start_turn() as turn:
            turn.user("Hello")
            with turn.start_step(model="gpt-4o") as step:
                step.usage = Usage(input_tokens=10, output_tokens=5)
                step.output_messages.append(Message(role="assistant", content="Hi!"))

2. Manual start/end::

    session = weave.start_session(agent_name="bot")
    turn = session.start_turn()
    turn.user("Hello")
    step = turn.start_step(model="gpt-4o")
    step.usage = Usage(input_tokens=10, output_tokens=5)
    step.output_messages.append(Message(role="assistant", content="Hi!"))
    step.end()
    turn.end()
    session.end()

3. Imperative batch::

    weave.log_session(agent_name="bot", turns=[...])

All paths emit OpenTelemetry spans via a TracerProvider.
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from opentelemetry.context import Context
from opentelemetry.trace import SpanKind, TracerProvider, set_span_in_context

if TYPE_CHECKING:
    from opentelemetry.trace import Span, Tracer
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Contextvars for current session/turn (thread/async-task safe)
# ---------------------------------------------------------------------------

_current_session: contextvars.ContextVar[Session | None] = contextvars.ContextVar(
    "weave_session", default=None
)
_current_turn: contextvars.ContextVar[Turn | None] = contextvars.ContextVar(
    "weave_turn", default=None
)

# OTel instrumentation library name used for the tracer.
_TRACER_NAME = "weave.session"

# Lazy-loaded references to session_otel attribute builders.
# These are loaded lazily to break the circular import:
# session.py -> session_otel.py -> session.py (for Message, Usage, Reasoning types).
_otel_builders: dict[str, Any] | None = None


def _get_otel_builders() -> dict[str, Any]:
    """Lazy-load attribute builder functions from session_otel to avoid circular import."""
    global _otel_builders  # noqa: PLW0603
    if _otel_builders is None:
        # Circular import avoidance: session_otel imports Message/Usage/Reasoning from this module
        from weave.trace.session_otel import (
            chat_attributes,
            execute_tool_attributes,
            invoke_agent_attributes,
        )

        _otel_builders = {
            "invoke_agent": invoke_agent_attributes,
            "chat": chat_attributes,
            "execute_tool": execute_tool_attributes,
        }
    return _otel_builders


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


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class Tool(BaseModel):
    """One tool execution within a step.

    Context manager that auto-calculates duration on exit.
    Creates an ``execute_tool`` span as child of the step span.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = ""
    arguments: str = ""
    result: str = ""
    duration_ms: int = 0

    _started_at: datetime | None = PrivateAttr(default=None)
    _ended: bool = PrivateAttr(default=False)

    # OTel fields
    _otel_span: Span | None = PrivateAttr(default=None)
    _conversation_id: str = PrivateAttr(default="")
    _conversation_name: str = PrivateAttr(default="")

    def end(self) -> None:
        """End the tool span. Calculates duration from start time."""
        if self._ended:
            return
        self._ended = True
        if self._started_at is not None:
            elapsed = datetime.now(timezone.utc) - self._started_at
            self.duration_ms = int(elapsed.total_seconds() * 1000)

        # Finalize and end OTel span
        if self._otel_span is not None:
            builders = _get_otel_builders()
            attrs = builders["execute_tool"](
                tool_name=self.name,
                tool_call_arguments=self.arguments,
                tool_call_result=self.result,
            )
            for k, v in attrs.items():
                self._otel_span.set_attribute(k, v)
            if self._conversation_id:
                self._otel_span.set_attribute(
                    "gen_ai.conversation.id", self._conversation_id
                )
            if self._conversation_name:
                self._otel_span.set_attribute(
                    "gen_ai.conversation.name", self._conversation_name
                )
            self._otel_span.end()

    def __enter__(self) -> Tool:
        self._started_at = datetime.now(timezone.utc)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        self.end()
        return False


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------


class Step(BaseModel):
    """One LLM invocation within a turn.

    Creates a ``chat`` span as child of the turn's ``invoke_agent`` span.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = ""
    provider_name: str = ""
    system_instructions: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    reasoning: Reasoning = Field(default_factory=Reasoning)
    finish_reasons: list[str] = Field(default_factory=list)
    input_messages: list[Message] = Field(default_factory=list)
    output_messages: list[Message] = Field(default_factory=list)
    tools: list[Tool] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _turn: Any = PrivateAttr(default=None)  # Turn back-reference
    _ended: bool = PrivateAttr(default=False)

    # OTel fields
    _otel_span: Span | None = PrivateAttr(default=None)
    _otel_context: Context | None = PrivateAttr(
        default=None
    )  # Context with this span active
    _tracer: Tracer | None = PrivateAttr(default=None)

    def start_tool(self, *, name: str, arguments: str = "") -> Tool:
        """Start a tool execution. Works as context manager or standalone."""
        t = Tool(name=name, arguments=arguments)
        self.tools.append(t)

        # In OTel mode, start an execute_tool span as child of this step
        if self._tracer is not None and self._otel_context is not None:
            span = self._tracer.start_span(
                "execute_tool",
                context=self._otel_context,
                kind=SpanKind.INTERNAL,
            )
            t._otel_span = span
            # Propagate conversation_id/conversation_name to the tool
            session = self._turn._session if self._turn else None
            if session:
                t._conversation_id = session.session_id
                t._conversation_name = session.session_name

        return t

    def end(self) -> None:
        """End the step. Sets final attributes and ends the OTel span."""
        if self._ended:
            return
        self._ended = True
        self.ended_at = datetime.now(timezone.utc)
        # End any open tool spans
        for t in self.tools:
            t.end()

        if self._otel_span is not None:
            builders = _get_otel_builders()
            attrs = builders["chat"](
                model=self.model,
                provider_name=self.provider_name,
                input_messages=self.input_messages or None,
                output_messages=self.output_messages or None,
                system_instructions=self.system_instructions or None,
                usage=self.usage,
                reasoning=self.reasoning,
                finish_reasons=self.finish_reasons or None,
            )
            for k, v in attrs.items():
                self._otel_span.set_attribute(k, v)
            # Propagate conversation_id/conversation_name from the session
            session = self._turn._session if self._turn else None
            if session and session.session_id:
                self._otel_span.set_attribute(
                    "gen_ai.conversation.id", session.session_id
                )
            if session and session.session_name:
                self._otel_span.set_attribute(
                    "gen_ai.conversation.name", session.session_name
                )
            self._otel_span.end()
        # Record step in parent turn for token aggregation
        if self._turn is not None:
            self._turn._flushed_steps.append(self)

    def __enter__(self) -> Step:
        self.started_at = datetime.now(timezone.utc)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        self.end()
        return False


# ---------------------------------------------------------------------------
# Turn
# ---------------------------------------------------------------------------


class Turn(BaseModel):
    """One user-agent exchange within a session.

    Creates an ``invoke_agent`` root span. Child ``chat`` spans
    are created by ``start_step()``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_name: str = ""
    model: str = ""
    messages: list[Message] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _session: Any = PrivateAttr(default=None)  # Session back-reference
    _flushed_steps: list[Step] = PrivateAttr(default_factory=list)
    _ended: bool = PrivateAttr(default=False)

    # OTel fields
    _otel_span: Span | None = PrivateAttr(default=None)
    _otel_context: Context | None = PrivateAttr(
        default=None
    )  # Context with this span active
    _tracer: Tracer | None = PrivateAttr(default=None)

    def user(self, content: str) -> Turn:
        """Record a user message for this turn."""
        self.messages.append(Message(role="user", content=content))
        return self

    def start_step(
        self,
        *,
        model: str = "",
        provider_name: str = "",
        system_instructions: list[str] | None = None,
    ) -> Step:
        """Start an LLM call step. Works as context manager or standalone."""
        step = Step(
            model=model or self.model or (self._session.model if self._session else ""),
            provider_name=provider_name,
            system_instructions=list(system_instructions or []),
        )
        step._turn = self

        # In OTel mode, start a chat span as child of this turn's invoke_agent span
        if self._tracer is not None and self._otel_context is not None:
            span = self._tracer.start_span(
                "chat",
                context=self._otel_context,
                kind=SpanKind.CLIENT,
            )
            step._otel_span = span
            step._otel_context = set_span_in_context(span)
            step._tracer = self._tracer

        return step

    def end(self) -> None:
        """End the turn. Flushes remaining data if needed."""
        if self._ended:
            return
        self._ended = True
        self.ended_at = datetime.now(timezone.utc)

        if self._otel_span is not None:
            # Set final attributes on invoke_agent span and end it
            # Collect all output messages from steps for the turn-level span
            all_output: list[Message] = []
            for step in self._flushed_steps:
                all_output.extend(step.output_messages)

            # Aggregate token usage across steps
            total_input = sum(s.usage.input_tokens for s in self._flushed_steps)
            total_output = sum(s.usage.output_tokens for s in self._flushed_steps)

            builders = _get_otel_builders()
            attrs = builders["invoke_agent"](
                agent_name=self.agent_name
                or (self._session.agent_name if self._session else ""),
                conversation_id=self._session.session_id if self._session else "",
                conversation_name=self._session.session_name if self._session else "",
                input_messages=self.messages or None,
                output_messages=all_output or None,
            )
            if total_input:
                attrs["gen_ai.usage.input_tokens"] = total_input
            if total_output:
                attrs["gen_ai.usage.output_tokens"] = total_output
            for k, v in attrs.items():
                self._otel_span.set_attribute(k, v)
            self._otel_span.end()

    def __enter__(self) -> Turn:
        self.started_at = datetime.now(timezone.utc)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        self.end()
        return False


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class Session(BaseModel):
    """A multi-turn agent session (maps to conversation_id on the server).

    Works as a context manager or standalone via start_session().
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str = ""
    session_name: str = ""
    agent_name: str = ""
    model: str = ""

    _current_turn: Turn | None = PrivateAttr(default=None)
    _ended: bool = PrivateAttr(default=False)
    _tracer: Tracer | None = PrivateAttr(default=None)

    def start_turn(
        self,
        *,
        model: str = "",
        agent_name: str = "",
    ) -> Turn:
        """Start a new turn. Works as context manager or standalone."""
        # End any open turn first
        if self._current_turn is not None:
            self._current_turn.end()

        turn = Turn(
            agent_name=agent_name or self.agent_name,
            model=model or self.model,
        )
        turn._session = self
        self._current_turn = turn

        # Start an invoke_agent root span (new trace per turn)
        if self._tracer is not None:
            span = self._tracer.start_span(
                "invoke_agent",
                context=Context(),  # new trace per turn
                kind=SpanKind.INTERNAL,
            )
            turn._otel_span = span
            turn._otel_context = set_span_in_context(span)
            turn._tracer = self._tracer

        # Set contextvars so get_current_turn() works from anywhere
        _current_session.set(self)
        _current_turn.set(turn)

        return turn

    def end(self) -> None:
        """End the session. Flushes any open turn."""
        if self._ended:
            return
        self._ended = True
        if self._current_turn is not None:
            self._current_turn.end()
        # Clear contextvars
        _current_session.set(None)
        _current_turn.set(None)

    def __enter__(self) -> Session:
        _current_session.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        self.end()
        return False


# ---------------------------------------------------------------------------
# LogResult
# ---------------------------------------------------------------------------


class LogResult(BaseModel):
    """Result of a batch log_* call."""

    session_id: str = ""
    trace_ids: list[str] = Field(default_factory=list)
    root_span_ids: list[str] = Field(default_factory=list)
    span_count: int = 0


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def start_session(
    *,
    agent_name: str = "",
    model: str = "",
    session_id: str = "",
    session_name: str = "",
    base_url: str = "",
    api_key: str = "",
    entity: str = "",
    project: str = "",
    _tracer_provider: TracerProvider | None = None,
) -> Session:
    """Start an agent session. Works as context manager or standalone.

    Emits OpenTelemetry spans via the given or auto-configured TracerProvider.

    Examples::

        # Context manager
        with weave.start_session(agent_name="bot") as session:
            with session.start_turn() as turn:
                turn.user("Hello")
                with turn.start_step(model="gpt-4o") as step:
                    step.usage = Usage(input_tokens=10, output_tokens=5)
                    step.output_messages.append(Message(role="assistant", content="Hi!"))

        # Manual
        session = weave.start_session(agent_name="bot")
        turn = session.start_turn()
        turn.user("Hello")
        step = turn.start_step(model="gpt-4o")
        step.usage = Usage(input_tokens=10, output_tokens=5)
        step.output_messages.append(Message(role="assistant", content="Hi!"))
        step.end()
        turn.end()
        session.end()

        # With explicit endpoint and auth (e.g. per-user delegated auth)
        session = weave.start_session(
            agent_name="bot",
            base_url="https://trace.wandb.ai",
            api_key="user-api-key",
            entity="my-entity",
            project="my-project",
        )

    Args:
        agent_name: Name of the agent.
        model: Default model name for turns/steps.
        session_id: Unique session identifier. Auto-generated if empty.
        session_name: Human-readable session name.
        base_url: Weave trace server base URL (e.g. ``https://trace.wandb.ai``).
            When provided with ``api_key``, creates a TracerProvider that exports
            to this endpoint with the given auth. Ignored if ``_tracer_provider``
            is given.
        api_key: W&B API key for authentication. Used with ``base_url``.
        entity: W&B entity name. Used with ``base_url`` for resource attributes.
        project: W&B project name. Used with ``base_url`` for resource attributes.
        _tracer_provider: Optional OTel TracerProvider. When provided, the
            session emits OTel spans via this provider. Takes precedence over
            ``base_url``/``api_key``.

    Returns:
        A ``Session`` instance.
    """
    session = Session(
        session_id=session_id or str(uuid.uuid4()),
        session_name=session_name,
        agent_name=agent_name,
        model=model,
    )

    if _tracer_provider is not None:
        session._tracer = _tracer_provider.get_tracer(_TRACER_NAME)
    elif base_url:
        # Build a TracerProvider with explicit endpoint and auth
        provider = _build_tracer_provider(
            base_url=base_url,
            api_key=api_key,
            entity=entity,
            project=project,
        )
        session._tracer = provider.get_tracer(_TRACER_NAME)
    else:
        # Auto-configure a TracerProvider
        from weave.otel.setup import ensure_tracer_provider

        provider = ensure_tracer_provider()
        session._tracer = provider.get_tracer(_TRACER_NAME)

    _current_session.set(session)
    return session


def get_current_session() -> Session | None:
    """Return the active session, or ``None`` if no session is active."""
    return _current_session.get()


def get_current_turn() -> Turn | None:
    """Return the active turn, or ``None`` if no turn is active."""
    return _current_turn.get()


def start_turn(
    *,
    model: str = "",
    agent_name: str = "",
) -> Turn:
    """Start a new turn under the current session.

    Convenience wrapper around ``get_current_session().start_turn(...)``.
    Works as a context manager or standalone (call ``.end()``).

    If no session is active, returns a disconnected ``Turn`` that records
    data locally but emits no OTel spans (safe no-op).

    Examples::

        with weave.start_turn() as turn:
            turn.user("Hello")
            with weave.start_step(model="gpt-4o") as step:
                ...

    Args:
        model: Default model name for steps in this turn.
        agent_name: Agent name for this turn.

    Returns:
        A ``Turn`` instance.
    """
    session = _current_session.get()
    if session is not None:
        return session.start_turn(model=model, agent_name=agent_name)
    # No active session — return a disconnected Turn (no OTel span)
    return Turn(model=model, agent_name=agent_name)


def start_step(
    *,
    model: str = "",
    provider_name: str = "",
    system_instructions: list[str] | None = None,
) -> Step:
    """Start an LLM call step under the current turn.

    Convenience wrapper around ``get_current_turn().start_step(...)``.
    Works as a context manager or standalone (call ``.end()``).

    If no turn is active, returns a disconnected ``Step`` that records
    data locally but emits no OTel spans (safe no-op).

    Examples::

        with weave.start_step(model="gpt-4o") as step:
            step.usage = Usage(input_tokens=100, output_tokens=50)
            step.output_messages.append(Message(role="assistant", content="Hi!"))

    Args:
        model: Model name for this LLM call.
        provider_name: Provider name (e.g. ``"openai"``).
        system_instructions: System instructions for this step.

    Returns:
        A ``Step`` instance.
    """
    turn = _current_turn.get()
    if turn is not None:
        return turn.start_step(
            model=model,
            provider_name=provider_name,
            system_instructions=system_instructions,
        )
    # No active turn — return a disconnected Step (no OTel span)
    return Step(
        model=model,
        provider_name=provider_name,
        system_instructions=list(system_instructions or []),
    )


def _build_tracer_provider(
    *,
    base_url: str,
    api_key: str,
    entity: str,
    project: str,
) -> TracerProvider:
    """Create an OTel TracerProvider that exports to a specific endpoint with auth."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as OTLPHTTPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from weave.otel.live_processor import LiveSpanProcessor
    from weave.version import VERSION

    headers: dict[str, str] = {}
    if api_key:
        headers["wandb-api-key"] = api_key

    base = base_url.rstrip("/")
    genai_endpoint = f"{base}/otel/v1/genai/traces"

    resource = Resource.create(
        {
            "service.name": "weave-session",
            "service.version": VERSION,
            "wandb.entity": entity,
            "wandb.project": project,
        }
    )
    provider = SDKTracerProvider(resource=resource)

    # Live span streaming
    provider.add_span_processor(
        LiveSpanProcessor(
            endpoint=f"{base}/otel/v1/genai/span/start",
            headers=headers,
        )
    )

    # Batch export
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPHTTPSpanExporter(
                endpoint=genai_endpoint,
                headers=headers,
            )
        )
    )

    return provider


def _get_tracer(
    _tracer_provider: TracerProvider | None = None,
) -> Tracer:
    """Get an OTel Tracer from the given or auto-configured provider."""
    if _tracer_provider is not None:
        return _tracer_provider.get_tracer(_TRACER_NAME)
    # Circular import avoidance: only needed when no explicit provider
    from weave.otel.setup import ensure_tracer_provider

    return ensure_tracer_provider().get_tracer(_TRACER_NAME)


def _emit_step_spans(
    *,
    tracer: Tracer,
    parent_context: Context,
    step_data: dict[str, Any],
    conversation_id: str,
    conversation_name: str,
    default_model: str,
) -> int:
    """Create a chat span (and child execute_tool spans) for one step dict.

    Returns the number of spans created.
    """
    builders = _get_otel_builders()
    span_count = 0

    # -- chat span --
    step_model = step_data.get("model", "") or default_model
    input_msgs = [
        Message(**m) if isinstance(m, dict) else m
        for m in step_data.get("input_messages", [])
    ]
    output_msgs = [
        Message(**m) if isinstance(m, dict) else m
        for m in step_data.get("output_messages", [])
    ]
    usage = Usage(
        input_tokens=step_data.get("input_tokens", 0),
        output_tokens=step_data.get("output_tokens", 0),
        reasoning_tokens=step_data.get("reasoning_tokens", 0),
    )
    reasoning = Reasoning(content=step_data.get("reasoning_content", ""))
    system_instructions = step_data.get("system_instructions", [])
    finish_reasons = step_data.get("finish_reasons", [])

    chat_span = tracer.start_span(
        "chat",
        context=parent_context,
        kind=SpanKind.CLIENT,
    )
    chat_context = set_span_in_context(chat_span)
    span_count += 1

    # -- execute_tool child spans --
    for tc in step_data.get("tool_calls", []):
        tool_span = tracer.start_span(
            "execute_tool",
            context=chat_context,
            kind=SpanKind.INTERNAL,
        )
        tool_attrs = builders["execute_tool"](
            tool_name=tc.get("tool_name", ""),
            tool_call_arguments=tc.get("arguments", ""),
            tool_call_result=tc.get("result", ""),
            tool_call_id=tc.get("tool_call_id", ""),
        )
        if conversation_id:
            tool_attrs["gen_ai.conversation.id"] = conversation_id
        if conversation_name:
            tool_attrs["gen_ai.conversation.name"] = conversation_name
        for k, v in tool_attrs.items():
            tool_span.set_attribute(k, v)
        tool_span.end()
        span_count += 1

    # Set chat span attributes and end
    chat_attrs = builders["chat"](
        model=step_model,
        provider_name=step_data.get("provider_name", ""),
        input_messages=input_msgs or None,
        output_messages=output_msgs or None,
        system_instructions=system_instructions or None,
        usage=usage,
        reasoning=reasoning,
        finish_reasons=finish_reasons or None,
    )
    if conversation_id:
        chat_attrs["gen_ai.conversation.id"] = conversation_id
    if conversation_name:
        chat_attrs["gen_ai.conversation.name"] = conversation_name
    for k, v in chat_attrs.items():
        chat_span.set_attribute(k, v)
    chat_span.end()

    return span_count


def log_session(
    *,
    turns: list[dict[str, Any]],
    agent_name: str = "",
    model: str = "",
    session_id: str = "",
    session_name: str = "",
    _tracer_provider: TracerProvider | None = None,
) -> LogResult:
    """Batch-ingest a complete session with all turns and steps.

    Use this when logging data after the fact (e.g., from an external runtime).
    Emits OTel spans: one ``invoke_agent`` per turn, with ``chat`` and
    ``execute_tool`` children for each step/tool call.

    Args:
        turns: List of turn dicts. Each turn should have ``messages`` (list of
            ``{"role": ..., "content": ...}`` dicts) and optionally ``steps``,
            ``model``, ``agent_name``, ``tool_calls``, etc.
        agent_name: Default agent name.
        model: Default model name.
        session_id: Unique session identifier. Auto-generated if empty.
        session_name: Human-readable session name.
        _tracer_provider: Optional OTel TracerProvider. When not provided,
            uses the auto-configured provider.

    Returns:
        A ``LogResult`` with session_id, trace_ids, and span_count.
    """
    sid = session_id or str(uuid.uuid4())
    tracer = _get_tracer(_tracer_provider)
    builders = _get_otel_builders()

    trace_ids: list[str] = []
    root_span_ids: list[str] = []
    total_span_count = 0

    for turn_data in turns:
        turn_agent = turn_data.get("agent_name", "") or agent_name
        turn_model = turn_data.get("model", "") or model

        # Messages on the turn
        turn_messages = [
            Message(**m) if isinstance(m, dict) else m
            for m in turn_data.get("messages", [])
        ]

        # Create invoke_agent span (new trace per turn)
        invoke_span = tracer.start_span(
            "invoke_agent",
            context=Context(),
            kind=SpanKind.INTERNAL,
        )
        invoke_context = set_span_in_context(invoke_span)
        total_span_count += 1

        # Collect output messages and usage from steps for the turn-level span
        all_output: list[Message] = []
        total_input_tokens = 0
        total_output_tokens = 0

        for step_data in turn_data.get("steps", []):
            total_span_count += _emit_step_spans(
                tracer=tracer,
                parent_context=invoke_context,
                step_data=step_data,
                conversation_id=sid,
                conversation_name=session_name,
                default_model=turn_model,
            )
            # Accumulate outputs/tokens for the invoke_agent span
            for m in step_data.get("output_messages", []):
                msg = Message(**m) if isinstance(m, dict) else m
                all_output.append(msg)
            total_input_tokens += step_data.get("input_tokens", 0)
            total_output_tokens += step_data.get("output_tokens", 0)

        # Set invoke_agent attributes and end
        invoke_attrs = builders["invoke_agent"](
            agent_name=turn_agent,
            conversation_id=sid,
            conversation_name=session_name,
            input_messages=turn_messages or None,
            output_messages=all_output or None,
        )
        if total_input_tokens:
            invoke_attrs["gen_ai.usage.input_tokens"] = total_input_tokens
        if total_output_tokens:
            invoke_attrs["gen_ai.usage.output_tokens"] = total_output_tokens
        for k, v in invoke_attrs.items():
            invoke_span.set_attribute(k, v)
        invoke_span.end()

        # Record IDs
        ctx = invoke_span.get_span_context()
        trace_ids.append(format(ctx.trace_id, "032x"))
        root_span_ids.append(format(ctx.span_id, "016x"))

    return LogResult(
        session_id=sid,
        trace_ids=trace_ids,
        root_span_ids=root_span_ids,
        span_count=total_span_count,
    )


def log_turn(
    *,
    session_id: str,
    messages: list[dict[str, str]] | None = None,
    steps: list[dict[str, Any]] | None = None,
    agent_name: str = "",
    model: str = "",
    session_name: str = "",
    _tracer_provider: TracerProvider | None = None,
) -> LogResult:
    """Batch-ingest a single turn into an existing session.

    Emits OTel spans: one ``invoke_agent`` root span with ``chat`` and
    ``execute_tool`` children for each step/tool call.

    Args:
        session_id: The session to append to.
        messages: List of message dicts (``{"role": ..., "content": ...}``).
        steps: List of step dicts.
        agent_name: Agent name for this turn.
        model: Model name for this turn.
        session_name: Human-readable session name.
        _tracer_provider: Optional OTel TracerProvider.

    Returns:
        A ``LogResult``.
    """
    turn_data: dict[str, Any] = {
        "messages": messages or [],
        "steps": steps or [],
        "agent_name": agent_name,
        "model": model,
    }
    return log_session(
        turns=[turn_data],
        agent_name=agent_name,
        model=model,
        session_id=session_id,
        session_name=session_name,
        _tracer_provider=_tracer_provider,
    )


def log_step(
    *,
    session_id: str,
    trace_id: str = "",
    parent_span_id: str = "",
    model: str = "",
    input_messages: list[dict[str, str]] | None = None,
    output_messages: list[dict[str, str]] | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
    reasoning_content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    system_instructions: list[str] | None = None,
    agent_name: str = "",
    session_name: str = "",
    _tracer_provider: TracerProvider | None = None,
) -> LogResult:
    """Batch-ingest a single step into an existing turn.

    Creates a ``chat`` OTel span with the ``conversation_id`` attribute set
    for server-side correlation. When ``trace_id`` and ``parent_span_id``
    are provided, the span is created as a child of that parent (proper
    OTel parent-child linkage). Otherwise, a new orphaned trace is created.

    Args:
        session_id: The session this turn belongs to.
        trace_id: The trace_id of the parent turn (hex string). When provided
            with ``parent_span_id``, creates proper OTel parent-child linkage.
        parent_span_id: The span_id of the parent invoke_agent span (hex string).
        model: Model name.
        input_messages: Messages sent to the LLM.
        output_messages: Messages produced by the LLM.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        reasoning_tokens: Number of reasoning tokens.
        reasoning_content: Reasoning/chain-of-thought text.
        tool_calls: List of tool call dicts.
        system_instructions: System instructions for this step.
        agent_name: Agent name.
        session_name: Human-readable session name.
        _tracer_provider: Optional OTel TracerProvider.

    Returns:
        A ``LogResult``.
    """
    step_data: dict[str, Any] = {
        "model": model,
        "input_messages": list(input_messages or []),
        "output_messages": list(output_messages or []),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "reasoning_content": reasoning_content,
        "tool_calls": list(tool_calls or []),
        "system_instructions": list(system_instructions or []),
    }

    tracer = _get_tracer(_tracer_provider)

    # Reconstruct parent context if the caller provided IDs from an existing turn
    if trace_id and parent_span_id:
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

        parent_ctx = SpanContext(
            trace_id=int(trace_id, 16),
            span_id=int(parent_span_id, 16),
            is_remote=True,
            trace_flags=TraceFlags(0x01),
        )
        parent_context = set_span_in_context(NonRecordingSpan(parent_ctx))
    else:
        parent_context = Context()

    span_count = _emit_step_spans(
        tracer=tracer,
        parent_context=parent_context,
        step_data=step_data,
        conversation_id=session_id,
        conversation_name=session_name,
        default_model=model,
    )

    return LogResult(
        session_id=session_id,
        trace_ids=[],
        root_span_ids=[],
        span_count=span_count,
    )
