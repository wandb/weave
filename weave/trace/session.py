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

Supports two modes:
- **OTel mode** (default): emits OpenTelemetry spans via a TracerProvider.
- **Legacy mode**: when ``_ingest_fn`` is provided, uses the structured ingest
  HTTP POST path for backward compatibility.
"""

from __future__ import annotations

import logging
import uuid
import warnings
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from opentelemetry.context import Context
from opentelemetry.trace import SpanKind, TracerProvider, set_span_in_context

if TYPE_CHECKING:
    from opentelemetry.trace import Span, Tracer
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)

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
# Helpers (legacy path)
# ---------------------------------------------------------------------------


def _get_project_id() -> str:
    """Get the current project_id from the active WeaveClient."""
    from weave.trace.context.weave_client_context import get_weave_client

    client = get_weave_client()
    if client is None:
        raise RuntimeError(
            "weave.init() must be called before using session logging. "
            "Call weave.init('your-project') first."
        )
    return f"{client.entity}/{client.project}"


def _ingest(
    req: tsi.GenAIConversationIngestReq,
) -> tsi.GenAIConversationIngestRes | None:
    """POST a structured conversation ingest request via the active WeaveClient."""
    from weave.trace.context.weave_client_context import get_weave_client

    client = get_weave_client()
    if client is None:
        logger.error("session logging: no active WeaveClient — call weave.init() first")
        return None

    try:
        return client.server.genai_conversation_ingest(req)
    except Exception:
        logger.exception("session logging: failed to flush")
        return None


def _msg_to_structured(msg: dict[str, str] | Message) -> tsi.GenAIStructuredMessage:
    if isinstance(msg, Message):
        return tsi.GenAIStructuredMessage(
            role=msg.role,
            content=msg.content,
            tool_call_id=msg.tool_call_id,
            tool_name=msg.tool_name,
        )
    return tsi.GenAIStructuredMessage(
        role=msg.get("role", "user"),  # type: ignore[arg-type]
        content=msg.get("content", ""),
        tool_call_id=msg.get("tool_call_id", ""),
        tool_name=msg.get("tool_name", ""),
    )


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class Tool(BaseModel):
    """One tool execution within a step.

    Context manager that auto-calculates duration on exit.

    **OTel mode:** Creates an ``execute_tool`` span as child of the step span.
    **Legacy mode:** Does not flush independently — included in parent step's flush.
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

    def _to_structured(self) -> tsi.GenAIStructuredToolCall:
        return tsi.GenAIStructuredToolCall(
            tool_name=self.name,
            arguments=self.arguments,
            result=self.result,
            duration_ms=self.duration_ms,
        )

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

    **OTel mode:** Creates a ``chat`` span as child of the turn's ``invoke_agent`` span.
    **Legacy mode:** Context manager that triggers incremental flush via parent turn on exit.
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
        """End the step. Triggers incremental flush via parent turn (legacy) or ends OTel span."""
        if self._ended:
            return
        self._ended = True
        self.ended_at = datetime.now(timezone.utc)
        # End any open tool spans
        for t in self.tools:
            t.end()

        if self._otel_span is not None:
            # OTel mode: set final attributes and end span
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
        elif self._turn is not None:
            # Legacy mode: flush via parent turn
            self._turn._flush_step(self)

    def _to_structured(self) -> tsi.GenAIStructuredStep:
        return tsi.GenAIStructuredStep(
            model=self.model,
            provider_name=self.provider_name,
            input_messages=[_msg_to_structured(m) for m in self.input_messages],
            output_messages=[_msg_to_structured(m) for m in self.output_messages],
            input_tokens=self.usage.input_tokens,
            output_tokens=self.usage.output_tokens,
            reasoning_tokens=self.usage.reasoning_tokens,
            reasoning_content=self.reasoning.content,
            started_at=self.started_at,
            ended_at=self.ended_at,
            finish_reasons=self.finish_reasons,
            tool_calls=[t._to_structured() for t in self.tools],
            system_instructions=self.system_instructions,
        )

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

    **OTel mode:** Creates an ``invoke_agent`` root span. Child ``chat`` spans
    are created by ``start_step()``.
    **Legacy mode:** Manages incremental flush state: the first step flush
    creates the root span and captures trace_id/root_span_id from the response.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_name: str = ""
    model: str = ""
    messages: list[Message] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _session: Any = PrivateAttr(default=None)  # Session back-reference
    _flushed_steps: list[Step] = PrivateAttr(default_factory=list)
    _trace_id: str = PrivateAttr(default="")
    _root_span_id: str = PrivateAttr(default="")
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
            # OTel mode: set final attributes on invoke_agent span and end it
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
        # Legacy mode
        elif not self._flushed_steps and self.messages:
            self._flush_minimal()

    # -- Legacy flush methods --------------------------------------------------

    def _flush_step(self, step: Step) -> None:
        """Flush a completed step. Called by Step.end() in legacy mode."""
        self._flushed_steps.append(step)

        if not self._trace_id:
            # First flush: full payload, server creates root + child
            self._post_turn(self._flushed_steps)
        else:
            # Incremental: only the new step under existing root
            self._post_turn([step])

    def _flush_minimal(self) -> None:
        """Flush a turn with no steps (e.g., errored turn with user message)."""
        self._post_turn([])

    def _post_turn(self, steps: list[Step]) -> None:
        """Build and POST the ingest payload."""
        incremental = bool(
            self._trace_id and self._root_span_id and len(self._flushed_steps) > 1
        )

        turn = tsi.GenAIStructuredTurn(
            messages=[_msg_to_structured(m) for m in self.messages],
            steps=[s._to_structured() for s in steps],
            agent_name=self.agent_name
            or (self._session.agent_name if self._session else ""),
            model=steps[0].model if steps else self.model,
            started_at=self.started_at,
            ended_at=self.ended_at,
        )

        if incremental:
            turn.trace_id = self._trace_id
            turn.parent_span_id = self._root_span_id

        session = self._session
        req = tsi.GenAIConversationIngestReq(
            project_id=session._project_id if session else "",
            conversation_id=session.session_id if session else "",
            conversation_name=session.session_name if session else "",
            agent_name=self.agent_name or (session.agent_name if session else ""),
            turns=[turn],
        )

        ingest_fn = (session._ingest_fn if session else None) or _ingest
        try:
            resp = ingest_fn(req)
        except Exception:
            logger.exception("session logging: failed to flush")
            return
        if resp is not None and not self._trace_id:
            if resp.trace_ids:
                self._trace_id = resp.trace_ids[0]
            if resp.root_span_ids:
                self._root_span_id = resp.root_span_ids[0]

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

    _project_id: str = PrivateAttr(default="")
    _ingest_fn: (
        Callable[
            [tsi.GenAIConversationIngestReq], tsi.GenAIConversationIngestRes | None
        ]
        | None
    ) = PrivateAttr(default=None)
    _current_turn: Turn | None = PrivateAttr(default=None)
    _ended: bool = PrivateAttr(default=False)

    # OTel fields
    _tracer: Tracer | None = PrivateAttr(default=None)

    @property
    def _use_otel(self) -> bool:
        """True when this session emits OTel spans (i.e., no legacy _ingest_fn)."""
        return self._tracer is not None

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

        # In OTel mode, start an invoke_agent root span (new trace per turn)
        if self._use_otel:
            span = self._tracer.start_span(
                "invoke_agent",
                context=Context(),  # new trace per turn
                kind=SpanKind.INTERNAL,
            )
            turn._otel_span = span
            turn._otel_context = set_span_in_context(span)
            turn._tracer = self._tracer

        return turn

    def end(self) -> None:
        """End the session. Flushes any open turn."""
        if self._ended:
            return
        self._ended = True
        if self._current_turn is not None:
            self._current_turn.end()

    def __enter__(self) -> Session:
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
    project_id: str = "",
    _ingest_fn: Callable[
        [tsi.GenAIConversationIngestReq], tsi.GenAIConversationIngestRes | None
    ]
    | None = None,
    _tracer_provider: TracerProvider | None = None,
) -> Session:
    """Start an agent session. Works as context manager or standalone.

    Requires ``weave.init()`` to have been called first, unless
    ``project_id`` and ``_ingest_fn`` are provided (for custom transport),
    or ``_tracer_provider`` is provided (OTel mode without weave.init).

    Two modes:
    - **OTel mode** (default): When ``_tracer_provider`` is given, or when
      ``_ingest_fn`` is *not* given. Emits OpenTelemetry spans.
    - **Legacy mode**: When ``_ingest_fn`` is given. Uses the old structured
      ingest HTTP POST path.

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

    Args:
        agent_name: Name of the agent.
        model: Default model name for turns/steps.
        session_id: Unique session identifier. Auto-generated if empty.
        session_name: Human-readable session name.
        project_id: Explicit project ID (``entity/project``). When provided,
            skips ``weave.init()`` check. Useful for custom transport.
        _ingest_fn: Optional custom ingest function. When provided, uses the
            legacy structured ingest path instead of OTel.
        _tracer_provider: Optional OTel TracerProvider. When provided, the
            session emits OTel spans via this provider.

    Returns:
        A ``Session`` instance.
    """
    # Determine mode: legacy (_ingest_fn) or OTel
    use_legacy = _ingest_fn is not None

    if use_legacy:
        # Legacy mode needs project_id
        resolved_project_id = project_id or _get_project_id()
    else:
        resolved_project_id = project_id

    session = Session(
        session_id=session_id or str(uuid.uuid4()),
        session_name=session_name,
        agent_name=agent_name,
        model=model,
    )
    session._project_id = resolved_project_id

    if use_legacy:
        warnings.warn(
            "_ingest_fn is deprecated. Use OTel-based tracing instead by passing "
            "a _tracer_provider, or rely on the default auto-configured provider.",
            DeprecationWarning,
            stacklevel=2,
        )
        session._ingest_fn = _ingest_fn
    elif _tracer_provider is not None:
        # Explicit OTel provider given
        session._tracer = _tracer_provider.get_tracer(_TRACER_NAME)
    else:
        # No provider and no _ingest_fn -- auto-configure a TracerProvider
        from weave.otel.setup import ensure_tracer_provider

        provider = ensure_tracer_provider()
        session._tracer = provider.get_tracer(_TRACER_NAME)

    return session


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

    Creates a standalone ``chat`` OTel span with the ``conversation_id``
    attribute set for server-side correlation. The ``trace_id`` and
    ``parent_span_id`` parameters are accepted for API compatibility but
    parent relationships are not reconstructed because our 128-bit span IDs
    do not fit in OTel's 64-bit span_id field.

    Args:
        session_id: The session this turn belongs to.
        trace_id: The trace_id of the parent turn (informational; not used
            for OTel parent linkage).
        parent_span_id: The root_span_id of the parent turn (informational).
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

    # Create a standalone chat span (new trace) with conversation_id for correlation
    span_count = _emit_step_spans(
        tracer=tracer,
        parent_context=Context(),
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


# ---------------------------------------------------------------------------
# Internal: dict → structured model converters
# ---------------------------------------------------------------------------


def _dict_to_structured_step(d: dict[str, Any]) -> tsi.GenAIStructuredStep:
    """Convert a step dict to a GenAIStructuredStep."""
    return tsi.GenAIStructuredStep(
        model=d.get("model", ""),
        provider_name=d.get("provider_name", ""),
        input_messages=[_msg_to_structured(m) for m in d.get("input_messages", [])],
        output_messages=[_msg_to_structured(m) for m in d.get("output_messages", [])],
        input_tokens=d.get("input_tokens", 0),
        output_tokens=d.get("output_tokens", 0),
        reasoning_tokens=d.get("reasoning_tokens", 0),
        reasoning_content=d.get("reasoning_content", ""),
        finish_reasons=d.get("finish_reasons", []),
        tool_calls=[
            tsi.GenAIStructuredToolCall(**tc) for tc in d.get("tool_calls", [])
        ],
        system_instructions=d.get("system_instructions", []),
    )
