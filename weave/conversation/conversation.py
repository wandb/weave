"""Weave Conversation SDK — structured logging for agent conversations.

Provides Python classes and functions for logging agent conversations
to Weave's Agents tab. All data flows through OpenTelemetry — the SDK
creates OTel spans with GenAI semantic convention attributes.

Each SDK class creates OTel spans with GenAI semantic convention
attributes when used as context managers.
"""

from __future__ import annotations

import logging
import types
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from typing_extensions import Self, deprecated

from weave.conversation.conversation_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
    llm_attributes,
)
from weave.conversation.types import (
    BlobPart,
    FilePart,
    JSONString,
    LogResult,
    MediaAttachment,
    Message,
    MessagePart,
    Reasoning,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolCallResponsePart,
    UriPart,
    Usage,
    _parse_data_url,
)
from weave.trace.settings import should_disable_weave, should_redact_pii
from weave.trace.util import Thread
from weave.utils import pii_redaction
from weave.utils.capture_info import get_capture_info

# OTel imports — kept top-level under a try/except guard so the module
# loads cleanly when opentelemetry is not installed. When unavailable,
# all span operations no-op silently.
_OTEL_AVAILABLE = True
try:
    from opentelemetry import context as otel_context
    from opentelemetry import trace as otel_trace
    from opentelemetry.context import Context
    from opentelemetry.trace import StatusCode
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )
except ImportError:
    _OTEL_AVAILABLE = False

if TYPE_CHECKING:
    from opentelemetry.context import Context as _OTelContext
    from opentelemetry.context import Token as _OTelToken
    from opentelemetry.trace import Span as _OTelSpan
    from opentelemetry.util.types import Attributes


# Re-export types for backwards compatibility with existing imports of
# `weave.conversation.conversation.Message` etc. The data classes themselves live
# in `weave.conversation.types` to break the import cycle with `conversation_otel`.
__all__ = [
    "LLM",
    "BlobPart",
    "Conversation",
    "FilePart",
    "LogResult",
    "MediaAttachment",
    "Message",
    "MessagePart",
    "Reasoning",
    "ReasoningPart",
    "SubAgent",
    "TextPart",
    "Tool",
    "ToolCallPart",
    "ToolCallResponsePart",
    "Turn",
    "UriPart",
    "Usage",
    "end_conversation",
    "end_llm",
    "end_subagent",
    "end_tool",
    "end_turn",
    "get_current_conversation",
    "get_current_llm",
    "get_current_span",
    "get_current_subagent",
    "get_current_tool",
    "get_current_turn",
    "log_conversation",
    "log_turn",
    "start_conversation",
    "start_llm",
    "start_subagent",
    "start_tool",
    "start_turn",
]


# ---------------------------------------------------------------------------
# Core span classes
# ---------------------------------------------------------------------------


# OTel tracer name — identifies the Conversation SDK as the source of these spans.
_TRACER_NAME = "weave.conversation"

logger = logging.getLogger(__name__)


def _capture_info_attrs() -> dict[str, str]:
    """Build weave.* client / system info attrs, gated by settings.

    Per-span (not OTel ``Resource``) so env-var toggles take effect on
    every emit, matching ``@op`` semantics in ``weave_client.py``.
    """
    return {f"weave.{k}": v for k, v in get_capture_info().items()}


# Forward-looking deprecation: OpenTelemetry is phasing out the Span Event API
# (``Span.add_event``), so we steer callers to ``set_attributes``,
# which Weave already records and surfaces in the Agents tab. ``add_event``
# still works and existing span-event data stays valid.
# https://opentelemetry.io/blog/2026/deprecating-span-events/
_ADD_EVENT_DEPRECATION_MESSAGE = (
    "`add_event` is deprecated; record this data with `set_attributes` instead. "
    "OpenTelemetry is phasing out the Span Event API (`Span.add_event`)."
)


class _SpanBase(BaseModel):
    """Shared config for span classes that use ``model`` as a field name."""

    model_config = ConfigDict(protected_namespaces=())

    _otel_span: _OTelSpan | None = PrivateAttr(default=None)
    _otel_token: _OTelToken | None = PrivateAttr(default=None)
    # Explicit OTel parent context, set by a parent span's ``start_llm`` /
    # ``start_tool`` / ``start_subagent`` factories (see ``_thread_otel_context``)
    # on the children they create so those children nest under the parent's span
    # regardless of what's on the ambient OTel context stack at ``__enter__`` time.
    _parent_otel_context: _OTelContext | None = PrivateAttr(default=None)
    # Force a brand-new root trace at ``__enter__`` (set by ``parent="ignore"``).
    # Only honored when no ``_parent_otel_context`` was provided.
    _force_new_trace: bool = PrivateAttr(default=False)

    def _thread_otel_context(self, child: _SpanBase) -> None:
        """Nest ``child``'s span under this one by handing it an explicit OTel
        parent context built from this span.

        No-op until this span has started (``_otel_span`` is set in
        ``_start_otel_span``); children created before then fall back to the
        ambient OTel context, matching the bare ``LLM()`` / ``Tool()`` path.
        """
        if self._otel_span is not None:
            child._parent_otel_context = otel_trace.set_span_in_context(self._otel_span)

    def _start_otel_span(
        self,
        name: str,
        *,
        new_trace: bool = False,
        start_time_ns: int | None = None,
    ) -> None:
        """Create an OTel span and attach it to the current context.

        ``start_time_ns`` lets the caller pass the logical start time when
        the SDK object was constructed (e.g. ``Turn.started_at``) so the
        OTel span timestamp matches the user-visible start, not the moment
        ``__enter__`` happened to run.

        When ``_parent_otel_context`` is set (a child threaded from its parent
        Turn/SubAgent), that context wins over ambient. ``new_trace`` is only
        honored when no explicit parent was provided.
        """
        if not _OTEL_AVAILABLE or should_disable_weave():
            return
        tracer = otel_trace.get_tracer(_TRACER_NAME)
        kwargs: dict[str, Any] = {}
        if start_time_ns is not None:
            kwargs["start_time"] = start_time_ns
        if self._parent_otel_context is not None:
            kwargs["context"] = self._parent_otel_context
        elif new_trace:
            kwargs["context"] = Context()
        self._otel_span = tracer.start_span(name, **kwargs)
        self._otel_token = otel_context.attach(
            otel_trace.set_span_in_context(self._otel_span)
        )
        # Stamp the active conversation's attributes on every span. Read from the
        # conversation contextvar (not OTel context) so they reach the root turn
        # span too, which starts in a fresh OTel Context to force a new trace.
        conversation = get_current_conversation()
        if conversation is not None and conversation.attributes:
            self._otel_span.set_attributes(conversation.attributes)

    def _end_otel_span(
        self, attrs: dict[str, Any], *, end_time_ns: int | None = None
    ) -> None:
        """Set attributes and end the OTel span, then detach context.

        ``end_time_ns`` lets the caller pass the logical end time when the
        SDK object recorded ``ended_at`` separately from when ``end()`` was
        called (e.g. the batch-logging path).
        """
        if not _OTEL_AVAILABLE or self._otel_span is None:
            return
        if self._otel_span.is_recording():
            for k, v in attrs.items():
                self._otel_span.set_attribute(k, v)
            if end_time_ns is not None:
                self._otel_span.end(end_time=end_time_ns)
            else:
                self._otel_span.end()
        if self._otel_token is not None:
            otel_context.detach(self._otel_token)
            self._otel_token = None

    def _record_otel_error(self, exc_val: BaseException) -> None:
        """Record an exception on the OTel span."""
        if not _OTEL_AVAILABLE or self._otel_span is None:
            return
        self._otel_span.set_status(StatusCode.ERROR, str(exc_val))
        self._otel_span.record_exception(exc_val)

    def _recording_span(self, operation: str, key: str | list[str]) -> _OTelSpan | None:
        """Return the OTel span if it's recording, else ``None``.

        Logs a warning naming the caller-facing fix when not recording.
        Silent when OTel isn't installed or Weave is disabled — both are
        intentional configs. Returning the span (instead of a bool) lets
        mypy narrow it through the caller's ``if`` guard.
        """
        if not _OTEL_AVAILABLE or should_disable_weave():
            return None
        key_repr = (
            "{" + ", ".join(map(repr, key)) + "}"
            if isinstance(key, list)
            else repr(key)
        )
        if self._otel_span is None:
            logger.warning(
                "%s(%s) ignored: span not started. Use `with` for live "
                "tracing, or log_turn() for batch ingest.",
                operation,
                key_repr,
            )
            return None
        if not self._otel_span.is_recording():
            logger.warning(
                "%s(%s) ignored: span already ended. Set attributes before "
                "exiting `with` or calling .end().",
                operation,
                key_repr,
            )
            return None
        return self._otel_span

    def traceparent(self) -> str:
        """Return this span's W3C ``traceparent`` string, or ``""`` if the span
        isn't started (or OTel is unavailable).

        Put the returned string on the wire (HTTP header, queue message, ...) and
        pass it back as ``parent=<traceparent>`` to an implicit ``start_*`` in
        another process to nest that work under this span. Uses the standard
        ``TraceContextTextMapPropagator`` so it interoperates with any
        W3C-compliant tracer.
        """
        if not _OTEL_AVAILABLE or self._otel_span is None:
            return ""
        carrier: dict[str, str] = {}
        TraceContextTextMapPropagator().inject(
            carrier, context=otel_trace.set_span_in_context(self._otel_span)
        )
        return carrier.get("traceparent", "")

    def set_attributes(self, attributes: dict[str, Any]) -> Self:
        """Stamp arbitrary OTel attributes on this span.

        Pass a dict whether you have one key or many — single-key callers
        use ``span.set_attributes({"weave.tag": "value"})``. Mirrors OTel's
        ``Span.set_attributes``.

        Must be called between span start and span end — i.e. inside a
        ``with`` block. Outside that window the call is a no-op and logs
        a warning. For batch ingest, populate the object's declared fields
        directly and pass it to ``log_turn`` / ``log_conversation``.
        """
        if span := self._recording_span("set_attributes", list(attributes)):
            span.set_attributes(attributes)
        return self

    @deprecated(_ADD_EVENT_DEPRECATION_MESSAGE)
    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> Self:
        """Record an OTel span event at a point in time within this span.

        .. deprecated::
            Record this data with ``set_attributes`` instead. OpenTelemetry is
            phasing out the Span Event API (``Span.add_event``).
            ``add_event`` still works and existing span-event data stays valid.
            See https://opentelemetry.io/blog/2026/deprecating-span-events/.

        Use for marker / lifecycle data — permission prompts (e.g.
        ``weave.permission_request``), lifecycle transitions (e.g.
        ``spawned`` / ``streaming`` / ``finished``), or any custom
        milestone that happens at a point in time within the span's
        lifetime (vs an attribute, which is a property of the span as a
        whole).

        Must be called between span start and span end (inside ``with``).
        Outside that window the call is a no-op and logs a warning.
        """
        if span := self._recording_span("add_event", name):
            span.add_event(name, attributes=attributes, timestamp=_to_ns(timestamp))
        return self

    if TYPE_CHECKING:
        # Declared for the type checker only; every concrete span class provides
        # the real ``__enter__`` / ``__exit__``. Lets the async wrappers below
        # delegate to them without mypy flagging that ``_SpanBase`` (never
        # instantiated directly) lacks them.
        def __enter__(self) -> Self: ...

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: types.TracebackType | None,
        ) -> Literal[False]: ...

    async def __aenter__(self) -> Self:
        """Async context-manager entry — delegates to the sync ``__enter__``.

        Span operations are synchronous (no I/O), so ``async with`` reuses the
        sync lifecycle; contextvars propagate across ``await``.
        """
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        return self.__exit__(exc_type, exc_val, exc_tb)


def _publish_media_content(
    *,
    content: bytes | str,
    uri: str,
    file_id: str,
    mime_type: str,
) -> str:
    """Create a Content object from raw media data and publish it.

    Returns the ``weave://`` ref URI string.
    """
    from weave.trace.api import publish
    from weave.type_wrappers.Content.content import Content

    content_obj: Content
    if content:
        if isinstance(content, str):
            content_obj = Content.from_base64(content, mimetype=mime_type or None)
        else:
            content_obj = Content.from_bytes(content, mimetype=mime_type or None)
    elif uri:
        if uri.startswith("data:"):
            content_obj = Content.from_data_url(uri)
        else:
            content_obj = Content.from_url(uri)
    elif file_id:
        raise ValueError(
            f"Cannot publish file_id {file_id!r} as Content; "
            "fetch the content from the provider first or use a URI"
        )
    else:
        raise ValueError("_publish_media_content requires content or uri")

    ref = publish(content_obj)
    # Coerce to a plain ``str``: ``ref.uri`` may be a ``_CallableStr`` subclass
    # that OTel attribute validation rejects.
    return str(getattr(ref, "uri", ref))


class Tool(_SpanBase):
    """One tool execution. Maps to an execute_tool OTel span.

    ``arguments`` and ``result`` use the ``JSONString`` annotation:
    callers can assign a dict / list / scalar and the SDK JSON-encodes
    it at construction or assignment. The stored value is always a
    string, matching the wire format per GenAI semconv.
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str = ""
    arguments: JSONString = ""
    result: JSONString = ""
    tool_call_id: str = ""
    tool_type: str = ""
    tool_description: str = ""
    tool_definitions: str = ""
    duration_ms: int = 0
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _ended: bool = PrivateAttr(default=False)
    _token: Token[Tool | None] | None = PrivateAttr(default=None)

    def _build_attrs(
        self, *, conversation_id: str, include_content: bool
    ) -> dict[str, Any]:
        """Build the full OTel attribute dict for this tool span.

        Single chokepoint shared by streaming (``end``) and batch
        (``_attrs_for_span``). Strips arguments/result when content is
        gated off; otherwise routes them through ``redact_pii_string``
        when redaction is enabled.
        """
        if include_content:
            arguments = self.arguments
            result = self.result
            if should_redact_pii():
                arguments = pii_redaction.redact_pii_string(arguments)
                result = pii_redaction.redact_pii_string(result)
        else:
            arguments = ""
            result = ""
        attrs = execute_tool_attributes(
            tool_name=self.name,
            conversation_id=conversation_id,
            tool_call_arguments=arguments,
            tool_call_result=result,
            tool_call_id=self.tool_call_id,
            tool_type=self.tool_type,
            tool_description=self.tool_description,
            tool_definitions=self.tool_definitions,
        )
        attrs.update(_capture_info_attrs())
        return attrs

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        if self.ended_at is None:
            self.ended_at = datetime.now(timezone.utc)
        if self.started_at is not None:
            elapsed = self.ended_at - self.started_at
            self.duration_ms = int(elapsed.total_seconds() * 1000)

        conversation = get_current_conversation()
        attrs = self._build_attrs(
            conversation_id=conversation.conversation_id if conversation else "",
            include_content=conversation.include_content if conversation else True,
        )

        if self._token is not None:
            try:
                _current_tool.reset(self._token)
            except ValueError:
                pass  # entered in a different context/thread; best-effort
            self._token = None

        self._end_otel_span(attrs, end_time_ns=_to_ns(self.ended_at))

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_tool.set(self)
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)
        start_ns = int(self.started_at.timestamp() * 1_000_000_000)
        self._start_otel_span(
            f"execute_tool {self.name}",
            new_trace=self._force_new_trace,
            start_time_ns=start_ns,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        if exc_val is not None:
            self._record_otel_error(exc_val)
        self.end()
        return False


class LLM(_SpanBase):
    """One LLM API call. Maps to a chat OTel span."""

    model: str = ""
    provider_name: str = ""
    response_id: str = ""
    response_model: str = ""
    output_type: str = ""
    system_instructions: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    reasoning: Reasoning = Field(default_factory=Reasoning)
    finish_reasons: list[str] = Field(default_factory=list)
    input_messages: list[Message] = Field(default_factory=list)
    output_messages: list[Message] = Field(default_factory=list)
    media_attachments: list[MediaAttachment] = Field(default_factory=list)
    request_temperature: float | None = None
    request_max_tokens: int | None = None
    request_top_p: float | None = None
    request_frequency_penalty: float | None = None
    request_presence_penalty: float | None = None
    request_seed: int | None = None
    request_stop_sequences: list[str] = Field(default_factory=list)
    request_choice_count: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _ended: bool = PrivateAttr(default=False)
    _token: Token[LLM | None] | None = PrivateAttr(default=None)
    _upload_threads: list[Thread] = PrivateAttr(default_factory=list)

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

        Creates a ``Content`` object from the provided data, publishes it
        to get a ``weave://`` ref, and stores only that ref.  Exactly one
        of ``content``, ``uri``, or ``file_id`` must be provided.

        The publish (which uploads the media) runs on a dedicated
        background thread so the call returns immediately without blocking
        the caller; one thread is dispatched per attachment so multiple
        uploads proceed in parallel. The placeholder ``MediaAttachment`` is
        appended synchronously and its ``ref`` is filled in once the upload
        completes. Refs are guaranteed populated before the span is emitted
        (the build path waits on the in-flight uploads via
        ``_await_uploads``).
        """
        sources = sum(bool(s) for s in (content, uri, file_id))
        if sources != 1:
            raise ValueError("Exactly one of content, uri, or file_id must be provided")

        if not modality and mime_type:
            prefix = mime_type.split("/", maxsplit=1)[0]
            if prefix in {"image", "audio", "video"}:
                modality = prefix

        attachment = MediaAttachment(
            ref="",
            modality=modality or "unknown",
            mime_type=mime_type,
        )
        self.media_attachments.append(attachment)
        thread = Thread(
            target=self._upload_media,
            kwargs={
                "attachment": attachment,
                "content": content,
                "uri": uri,
                "file_id": file_id,
                "mime_type": mime_type,
            },
            name="weave-conversation-media-upload",
            daemon=True,
        )
        thread.start()
        self._upload_threads.append(thread)
        return self

    def _upload_media(
        self,
        *,
        attachment: MediaAttachment,
        content: bytes | str,
        uri: str,
        file_id: str,
        mime_type: str,
    ) -> None:
        """Publish one media attachment and record its ref.

        Runs on a background thread dispatched by ``attach_media``. On
        success the ``weave://`` ref is written back onto ``attachment``.
        Failures are logged and leave the ref empty; ``_await_uploads``
        drops empty-ref attachments so a failed upload never emits a
        broken URI part.
        """
        try:
            attachment.ref = _publish_media_content(
                content=content, uri=uri, file_id=file_id, mime_type=mime_type
            )
        except Exception:
            logger.exception("Failed to publish media attachment for chat span")

    def _await_uploads(self) -> None:
        """Block until all in-flight media uploads finish.

        Called before building span attributes so every attachment has its
        ``weave://`` ref populated. Attachments whose upload failed (empty
        ref) are dropped so the emitted span never carries a broken URI.
        """
        if not self._upload_threads:
            return
        for thread in self._upload_threads:
            thread.join()
        self._upload_threads.clear()
        self.media_attachments = [m for m in self.media_attachments if m.ref]

    def attach_media_url(self, url: str, *, modality: str = "") -> LLM:
        """Attach a media URL to this LLM call.

        Convenience over ``attach_media`` for the common case where the
        caller has a URL string from an upstream message. ``data:`` URLs
        are parsed into bytes and published; plain URIs are fetched and
        published. Empty URLs are ignored. Returns ``self`` for chaining.
        """
        if not url:
            return self
        if url.startswith("data:"):
            mime_type, content = _parse_data_url(url)
            return self.attach_media(
                content=content, mime_type=mime_type, modality=modality
            )
        return self.attach_media(uri=url, modality=modality)

    def record(
        self,
        *,
        input_messages: list[Message] | None = None,
        output_messages: list[Message] | None = None,
        media_attachments: list[MediaAttachment] | None = None,
        usage: Usage | None = None,
        reasoning: Reasoning | str | None = None,
        response_id: str | None = None,
        response_model: str | None = None,
        finish_reasons: list[str] | None = None,
        output_type: str | None = None,
    ) -> LLM:
        """Set multiple LLM-call fields in one call.

        Manually-instrumented agents typically build up a chat span by
        assigning eight or more individual fields at the end of an LLM
        call (``input_messages``, ``output_messages``, ``usage``,
        ``response_id``, etc.). ``record(...)`` collapses those into a
        single keyword call so the recording site stays compact.

        Only fields explicitly passed (non-``None``) are applied —
        existing values are preserved. ``reasoning`` accepts either a
        ``Reasoning`` instance or a plain string (wrapped automatically).
        Returns ``self`` for chaining.
        """
        if input_messages is not None:
            self.input_messages = input_messages
        if output_messages is not None:
            self.output_messages = output_messages
        if media_attachments is not None:
            self.media_attachments = media_attachments
        if usage is not None:
            self.usage = usage
        if reasoning is not None:
            self.reasoning = (
                Reasoning(content=reasoning)
                if isinstance(reasoning, str)
                else reasoning
            )
        if response_id is not None:
            self.response_id = response_id
        if response_model is not None:
            self.response_model = response_model
        if finish_reasons is not None:
            self.finish_reasons = finish_reasons
        if output_type is not None:
            self.output_type = output_type
        return self

    def _build_attrs(
        self, *, conversation_id: str, include_content: bool
    ) -> dict[str, Any]:
        """Build the full OTel attribute dict for this chat span.

        Single chokepoint shared by streaming (``end``) and batch
        (``_attrs_for_span``). All five content-bearing fields go
        ``None`` when content is gated off — notably this includes
        ``reasoning``, which previously bypassed the gate and leaked
        into ``gen_ai.output.messages``.
        """
        # Block on any background media uploads so every attachment's
        # weave:// ref is populated before it is serialized into attrs.
        self._await_uploads()

        input_messages: list[Message] | None
        output_messages: list[Message] | None
        system_instructions: list[str] | None
        media_attachments: list[MediaAttachment] | None
        reasoning: Reasoning | None
        if include_content:
            input_messages = self.input_messages
            output_messages = self.output_messages
            system_instructions = self.system_instructions
            media_attachments = self.media_attachments
            reasoning = self.reasoning
            if should_redact_pii():
                input_messages = pii_redaction.redact_messages(input_messages)
                output_messages = pii_redaction.redact_messages(output_messages)
                system_instructions = pii_redaction.redact_system_instructions(
                    system_instructions
                )
                if reasoning.content:
                    reasoning = Reasoning(
                        content=pii_redaction.redact_pii_string(reasoning.content)
                    )
        else:
            input_messages = None
            output_messages = None
            system_instructions = None
            media_attachments = None
            reasoning = None
        attrs = llm_attributes(
            model=self.model,
            provider_name=self.provider_name,
            conversation_id=conversation_id,
            input_messages=input_messages,
            output_messages=output_messages,
            media_attachments=media_attachments,
            system_instructions=system_instructions,
            usage=self.usage,
            reasoning=reasoning,
            finish_reasons=self.finish_reasons,
            response_id=self.response_id,
            response_model=self.response_model,
            output_type=self.output_type,
            request_temperature=self.request_temperature,
            request_max_tokens=self.request_max_tokens,
            request_top_p=self.request_top_p,
            request_frequency_penalty=self.request_frequency_penalty,
            request_presence_penalty=self.request_presence_penalty,
            request_seed=self.request_seed,
            request_stop_sequences=self.request_stop_sequences,
            request_choice_count=self.request_choice_count,
        )
        attrs.update(_capture_info_attrs())
        return attrs

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        if self.ended_at is None:
            self.ended_at = datetime.now(timezone.utc)

        conversation = get_current_conversation()
        attrs = self._build_attrs(
            conversation_id=conversation.conversation_id if conversation else "",
            include_content=conversation.include_content if conversation else True,
        )

        if self._token is not None:
            try:
                _current_llm.reset(self._token)
            except ValueError:
                pass  # entered in a different context/thread; best-effort
            self._token = None

        self._end_otel_span(attrs, end_time_ns=_to_ns(self.ended_at))

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_llm.set(self)
        start_ns = (
            int(self.started_at.timestamp() * 1_000_000_000)
            if self.started_at is not None
            else None
        )
        self._start_otel_span(
            f"chat {self.model}",
            new_trace=self._force_new_trace,
            start_time_ns=start_ns,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        if exc_val is not None:
            self._record_otel_error(exc_val)
        self.end()
        return False


class SubAgent(_SpanBase):
    """A delegated agent invocation within a turn.

    Maps to a nested invoke_agent OTel span in the same trace.
    """

    name: str = ""
    model: str = ""
    agent_id: str = ""
    agent_description: str = ""
    agent_version: str = ""
    system_instructions: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _ended: bool = PrivateAttr(default=False)
    # Token for this sub-agent's push onto the container stack (see
    # ``_current_container``); reset on ``end()``.
    _container_token: Token[Turn | SubAgent | None] | None = PrivateAttr(default=None)

    def start_llm(
        self,
        *,
        model: str = "",
        provider_name: str = "",
        system_instructions: list[str] | None = None,
    ) -> LLM:
        """Start an LLM call within this sub-agent.

        The returned LLM sets the ``_current_llm`` contextvar when entered
        (``with``), so ``get_current_llm()`` reflects it inside the block. Pins
        the LLM's OTel parent to this SubAgent's span when the SubAgent has been
        entered.
        """
        llm = LLM(
            model=model or self.model,
            provider_name=provider_name,
            system_instructions=system_instructions or [],
        )
        self._thread_otel_context(llm)
        return llm

    def start_tool(
        self, *, name: str, arguments: str = "", tool_call_id: str = ""
    ) -> Tool:
        """Start a tool execution within this sub-agent.

        Pins the Tool's OTel parent to this SubAgent's span when the SubAgent
        has been entered.
        """
        tool = Tool(name=name, arguments=arguments, tool_call_id=tool_call_id)
        self._thread_otel_context(tool)
        return tool

    def start_subagent(
        self,
        *,
        name: str,
        model: str = "",
        system_instructions: list[str] | None = None,
    ) -> SubAgent:
        """Start a nested sub-agent under this one.

        Pins the nested SubAgent's OTel parent to this SubAgent's span when
        this SubAgent has been entered. Signature mirrors ``Turn.start_subagent``
        so the top-level ``start_subagent`` can delegate here without dropping
        ``system_instructions``.
        """
        sub = SubAgent(
            name=name,
            model=model or self.model,
            system_instructions=system_instructions or [],
        )
        self._thread_otel_context(sub)
        return sub

    # Deprecated aliases — the factory methods were renamed to ``start_*`` to
    # match the module-level ``start_*`` functions.
    @deprecated("`llm` is deprecated; use `start_llm` instead.")
    def llm(
        self,
        *,
        model: str = "",
        provider_name: str = "",
        system_instructions: list[str] | None = None,
    ) -> LLM:
        """Deprecated alias for :meth:`start_llm`."""
        return self.start_llm(
            model=model,
            provider_name=provider_name,
            system_instructions=system_instructions,
        )

    @deprecated("`tool` is deprecated; use `start_tool` instead.")
    def tool(self, *, name: str, arguments: str = "", tool_call_id: str = "") -> Tool:
        """Deprecated alias for :meth:`start_tool`."""
        return self.start_tool(
            name=name, arguments=arguments, tool_call_id=tool_call_id
        )

    def record(
        self,
        *,
        name: str | None = None,
        model: str | None = None,
        system_instructions: list[str] | None = None,
        agent_id: str | None = None,
        agent_description: str | None = None,
        agent_version: str | None = None,
    ) -> SubAgent:
        """Set multiple sub-agent fields in one call.

        Collapses the per-field assignments a manually-instrumented agent
        otherwise makes on a sub-agent (``system_instructions``, ``agent_id``,
        ...) into a single keyword call. Only fields explicitly passed
        (non-``None``) are applied — existing values are preserved. Returns
        ``self`` for chaining. Mirrors ``Turn.record`` / ``LLM.record``.

        Note: on the streaming (``with``) path the sub-agent span is named
        from ``name`` at ``__enter__``, so set ``name`` via ``start_subagent``
        / ``turn.subagent`` rather than ``record`` if you need the span name
        to reflect it; ``record`` still updates the ``gen_ai.agent.name``
        attribute.
        """
        if name is not None:
            self.name = name
        if model is not None:
            self.model = model
        if system_instructions is not None:
            self.system_instructions = system_instructions
        if agent_id is not None:
            self.agent_id = agent_id
        if agent_description is not None:
            self.agent_description = agent_description
        if agent_version is not None:
            self.agent_version = agent_version
        return self

    def _build_attrs(
        self, *, conversation_id: str, conversation_name: str, include_content: bool
    ) -> dict[str, Any]:
        """Build the full OTel attribute dict for this sub-agent span.

        Shared between streaming (``end``) and batch (``_attrs_for_span``).
        ``system_instructions`` is the only content-bearing field — it is
        gated by ``include_content`` and PII-redacted, mirroring ``Turn``;
        the identifiers are always emitted.
        """
        system_instructions: list[str] | None
        if include_content:
            system_instructions = self.system_instructions
            if should_redact_pii():
                system_instructions = pii_redaction.redact_system_instructions(
                    system_instructions
                )
        else:
            system_instructions = None
        attrs = invoke_agent_attributes(
            agent_name=self.name,
            model=self.model,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            system_instructions=system_instructions,
            agent_id=self.agent_id,
            agent_description=self.agent_description,
            agent_version=self.agent_version,
        )
        attrs.update(_capture_info_attrs())
        return attrs

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        if self.ended_at is None:
            self.ended_at = datetime.now(timezone.utc)

        conversation = get_current_conversation()
        attrs = self._build_attrs(
            conversation_id=conversation.conversation_id if conversation else "",
            conversation_name=conversation.conversation_name if conversation else "",
            include_content=conversation.include_content if conversation else True,
        )

        if self._container_token is not None:
            try:
                _current_container.reset(self._container_token)
            except ValueError:
                pass  # entered in a different context/thread; best-effort
            self._container_token = None

        self._end_otel_span(attrs, end_time_ns=_to_ns(self.ended_at))

    def __enter__(self) -> Self:
        if self._container_token is None:
            self._container_token = _current_container.set(self)
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)
        start_ns = int(self.started_at.timestamp() * 1_000_000_000)
        self._start_otel_span(
            f"invoke_agent {self.name}",
            new_trace=self._force_new_trace,
            start_time_ns=start_ns,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        if exc_val is not None:
            self._record_otel_error(exc_val)
        self.end()
        return False


# ---------------------------------------------------------------------------
# Turn and Conversation
# ---------------------------------------------------------------------------


class Turn(_SpanBase):
    """One user-agent exchange. Maps to an invoke_agent OTel span.

    By default each turn starts its own OTel trace (``continue_parent_trace=False``)
    so the Agents tab shows one trace per turn. Set ``continue_parent_trace=True``
    on the Conversation (or directly on the Turn) when an outer trace is already
    active and you want the agent invocation to nest inside it — e.g. inside
    a fastapi-instrumented request.
    """

    agent_name: str = ""
    model: str = ""
    agent_id: str = ""
    agent_description: str = ""
    agent_version: str = ""
    system_instructions: list[str] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    spans: list[LLM | Tool | SubAgent] = Field(default_factory=list)
    continue_parent_trace: bool = False
    started_at: datetime | None = None
    ended_at: datetime | None = None

    _ended: bool = PrivateAttr(default=False)
    _token: Token[Turn | None] | None = PrivateAttr(default=None)
    # Token for this turn's push onto the container stack (see
    # ``_current_container``). A Turn pushes itself so its children nest under
    # it; this shadows any active sub-agent for the turn's lifetime (restored on
    # ``end()``), which replaces the old explicit "drop the sub-agent" step.
    _container_token: Token[Turn | SubAgent | None] | None = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)

    def user(self, content: str) -> Turn:
        """Append a user message mid-turn."""
        self.messages.append(Message(role="user", content=content))
        return self

    # Like ``SubAgent``, pin children to this turn's captured OTel context (via
    # ``_thread_otel_context``) so a child built inside ``with turn:`` but
    # entered after the turn exits still nests under it rather than becoming a
    # detached root span. No-op until the turn is entered. See ``_SpanBase``.
    def start_llm(
        self,
        *,
        model: str = "",
        provider_name: str = "",
        system_instructions: list[str] | None = None,
    ) -> LLM:
        """Start an LLM call (chat span, child of this turn).

        The returned LLM sets the ``_current_llm`` contextvar when entered
        (``with``), so ``get_current_llm()`` reflects it inside the block.
        """
        llm = LLM(
            model=model or self.model,
            provider_name=provider_name,
            system_instructions=system_instructions or [],
        )
        self._thread_otel_context(llm)
        return llm

    def start_tool(
        self, *, name: str, arguments: str = "", tool_call_id: str = ""
    ) -> Tool:
        """Start a tool execution (execute_tool span, child of this turn)."""
        tool = Tool(name=name, arguments=arguments, tool_call_id=tool_call_id)
        self._thread_otel_context(tool)
        return tool

    def start_subagent(
        self,
        *,
        name: str,
        model: str = "",
        system_instructions: list[str] | None = None,
    ) -> SubAgent:
        """Start a sub-agent invocation (nested invoke_agent span, same trace)."""
        sub = SubAgent(
            name=name,
            model=model or self.model,
            system_instructions=system_instructions or [],
        )
        self._thread_otel_context(sub)
        return sub

    # Deprecated aliases — the factory methods were renamed to ``start_*`` to
    # match the module-level ``start_*`` functions.
    @deprecated("`llm` is deprecated; use `start_llm` instead.")
    def llm(
        self,
        *,
        model: str = "",
        provider_name: str = "",
        system_instructions: list[str] | None = None,
    ) -> LLM:
        """Deprecated alias for :meth:`start_llm`."""
        return self.start_llm(
            model=model,
            provider_name=provider_name,
            system_instructions=system_instructions,
        )

    @deprecated("`tool` is deprecated; use `start_tool` instead.")
    def tool(self, *, name: str, arguments: str = "", tool_call_id: str = "") -> Tool:
        """Deprecated alias for :meth:`start_tool`."""
        return self.start_tool(
            name=name, arguments=arguments, tool_call_id=tool_call_id
        )

    @deprecated("`subagent` is deprecated; use `start_subagent` instead.")
    def subagent(
        self,
        *,
        name: str,
        model: str = "",
        system_instructions: list[str] | None = None,
    ) -> SubAgent:
        """Deprecated alias for :meth:`start_subagent`."""
        return self.start_subagent(
            name=name, model=model, system_instructions=system_instructions
        )

    def record(
        self,
        *,
        messages: list[Message] | None = None,
        system_instructions: list[str] | None = None,
        agent_name: str | None = None,
        model: str | None = None,
        agent_id: str | None = None,
        agent_description: str | None = None,
        agent_version: str | None = None,
    ) -> Turn:
        """Set multiple turn fields in one call.

        Collapses the per-field assignments a manually-instrumented agent
        otherwise makes on a turn (``system_instructions``, ``agent_id``,
        ...) into a single keyword call. Only fields explicitly passed
        (non-``None``) are applied — existing values are preserved.
        ``messages`` **replaces** the turn's existing messages (unlike
        ``Turn.user(...)``, which appends a single message). Returns
        ``self`` for chaining. Mirrors ``LLM.record``.

        Note: on the streaming (``with``) path the turn span is named from
        ``agent_name`` at ``__enter__``, so set ``agent_name`` via
        ``start_turn`` rather than ``record`` if you need the span name to
        reflect it; ``record`` still updates the ``gen_ai.agent.name``
        attribute.
        """
        if messages is not None:
            self.messages = messages
        if system_instructions is not None:
            self.system_instructions = system_instructions
        if agent_name is not None:
            self.agent_name = agent_name
        if model is not None:
            self.model = model
        if agent_id is not None:
            self.agent_id = agent_id
        if agent_description is not None:
            self.agent_description = agent_description
        if agent_version is not None:
            self.agent_version = agent_version
        return self

    def _build_attrs(
        self, *, conversation_id: str, conversation_name: str, include_content: bool
    ) -> dict[str, Any]:
        """Build the full OTel attribute dict for this turn span.

        Shared by streaming (``end``) and batch (``log_turn``). The Turn
        carries user messages; ``include_content=False`` strips them at
        source so Presidio is never called for already-dropped content.
        """
        messages: list[Message] | None
        system_instructions: list[str] | None
        if include_content:
            messages = self.messages
            system_instructions = self.system_instructions
            if should_redact_pii():
                messages = pii_redaction.redact_messages(messages)
                system_instructions = pii_redaction.redact_system_instructions(
                    system_instructions
                )
        else:
            messages = None
            system_instructions = None
        attrs = invoke_agent_attributes(
            agent_name=self.agent_name,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            model=self.model,
            input_messages=messages,
            system_instructions=system_instructions,
            agent_id=self.agent_id,
            agent_description=self.agent_description,
            agent_version=self.agent_version,
        )
        attrs.update(_capture_info_attrs())
        return attrs

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        if self.ended_at is None:
            self.ended_at = datetime.now(timezone.utc)

        conversation = get_current_conversation()
        attrs = self._build_attrs(
            conversation_id=conversation.conversation_id if conversation else "",
            conversation_name=conversation.conversation_name if conversation else "",
            include_content=conversation.include_content if conversation else True,
        )

        if self._token is not None:
            try:
                _current_turn.reset(self._token)
            except ValueError:
                pass  # entered in a different context/thread; best-effort
            self._token = None

        if self._container_token is not None:
            try:
                _current_container.reset(self._container_token)
            except ValueError:
                pass  # entered in a different context/thread; best-effort
            self._container_token = None

        self._end_otel_span(attrs, end_time_ns=_to_ns(self.ended_at))

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_turn.set(self)
        # Push the turn as the current container so its implicit children nest
        # under it. Entering a turn shadows any active sub-agent for the turn's
        # lifetime (restored on end()); the container stack replaces the old
        # explicit "drop the sub-agent" step.
        if self._container_token is None:
            self._container_token = _current_container.set(self)
        start_ns = (
            int(self.started_at.timestamp() * 1_000_000_000)
            if self.started_at is not None
            else None
        )
        self._start_otel_span(
            f"invoke_agent {self.agent_name}",
            new_trace=not self.continue_parent_trace,
            start_time_ns=start_ns,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        if exc_val is not None:
            self._record_otel_error(exc_val)
        self.end()
        return False


class Conversation(BaseModel):
    """A conversation. Groups turns by conversation_id (no span).

    ``continue_parent_trace`` controls trace isolation for the turns this
    conversation creates. Default ``False`` means each turn starts its own OTel
    trace (the right choice for the standalone Agents tab view). Set ``True``
    when the application has an outer trace (e.g. a fastapi-instrumented
    request) that should contain the agent invocation.

    .. deprecated::
        Prefer ``weave.start_turn(parent=<traceparent>)`` to nest a turn under a
        specific (in-process or remote) parent; ``continue_parent_trace`` only
        inherits the ambient in-process OTel trace and will be removed in a
        future release.
    """

    model_config = ConfigDict(protected_namespaces=())

    conversation_id: str = ""
    conversation_name: str = ""
    # Conversation-level defaults each turn inherits (its own value wins).
    # system_instructions is excluded — it varies per turn.
    agent_name: str = ""
    model: str = ""
    agent_id: str = ""
    agent_description: str = ""
    agent_version: str = ""
    include_content: bool = True
    continue_parent_trace: bool = False
    # Attributes stamped on every span this conversation emits (e.g. an integration
    # identity). dict[str, Any] like set_attributes — Attributes is a
    # TYPE_CHECKING-only import, but Pydantic resolves field types at runtime.
    attributes: dict[str, Any] = Field(default_factory=dict)

    _ended: bool = PrivateAttr(default=False)
    _token: Token[Conversation | None] | None = PrivateAttr(default=None)
    _current_turn: Turn | None = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())

    def start_turn(
        self,
        *,
        user_message: str = "",
        model: str = "",
        agent_name: str = "",
        agent_id: str = "",
        agent_description: str = "",
        agent_version: str = "",
        system_instructions: list[str] | None = None,
    ) -> Turn:
        """Create a new turn. Auto-ends the previous turn if still open.

        The returned turn sets the ``_current_turn`` contextvar when entered
        (``with``), so ``get_current_turn()`` reflects it inside the block.
        Each of ``agent_name`` / ``model`` / ``agent_id`` / ``agent_description``
        / ``agent_version`` falls back to the conversation's default when left
        empty; ``continue_parent_trace`` is inherited. Override any of them later
        via ``turn.record(...)``.

        ``system_instructions`` (the agent's system prompt) is carried on the
        turn's invoke_agent span; it can also be set later via attribute
        assignment on the returned ``Turn``, mirroring ``start_llm``.
        """
        if self._current_turn is not None and not self._current_turn._ended:
            self._current_turn.end()
        turn = Turn(
            agent_name=agent_name or self.agent_name,
            model=model or self.model,
            agent_id=agent_id or self.agent_id,
            agent_description=agent_description or self.agent_description,
            agent_version=agent_version or self.agent_version,
            system_instructions=system_instructions or [],
            continue_parent_trace=self.continue_parent_trace,
        )
        if user_message:
            turn.messages.append(Message(role="user", content=user_message))
        self._current_turn = turn
        return turn

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        if self._current_turn is not None and not self._current_turn._ended:
            self._current_turn.end()
        if self._token is not None:
            try:
                _current_conversation.reset(self._token)
            except ValueError:
                pass  # entered in a different context/thread; best-effort
            self._token = None

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_conversation.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        self.end()
        return False

    async def __aenter__(self) -> Self:
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        return self.__exit__(exc_type, exc_val, exc_tb)


# ---------------------------------------------------------------------------
# Contextvars
# ---------------------------------------------------------------------------

_current_conversation: ContextVar[Conversation | None] = ContextVar(
    "_current_conversation", default=None
)
_current_turn: ContextVar[Turn | None] = ContextVar("_current_turn", default=None)
# Single "container" stack: the innermost open Turn or SubAgent. Turn and
# SubAgent push themselves here on ``__enter__`` and pop on ``end()``; LLM and
# Tool are leaves and never push. Implicit ``start_*`` nest under whatever is on
# top, so there is no per-type priority and no "drop the stale sub-agent" step —
# entering a Turn simply shadows any active sub-agent until the Turn ends.
_current_container: ContextVar[Turn | SubAgent | None] = ContextVar(
    "_current_container", default=None
)
_current_llm: ContextVar[LLM | None] = ContextVar("_current_llm", default=None)
# Tools are leaves (never a parent), but tracked here so end_tool() /
# get_current_tool() can operate on the innermost active tool, mirroring _current_llm.
_current_tool: ContextVar[Tool | None] = ContextVar("_current_tool", default=None)


# ---------------------------------------------------------------------------
# Top-level functions
# ---------------------------------------------------------------------------


# ``parent=`` override accepted by the implicit ``start_*`` factories. The
# sentinel ``"ignore"`` forces a brand-new root trace (à la LangSmith's
# ``parent="ignore"``); any other plain string is treated as a W3C
# ``traceparent`` to adopt (cross-process).
_IGNORE_PARENT = "ignore"


def _otel_context_from_traceparent(traceparent: str) -> _OTelContext | None:
    """Build an OTel parent context from a W3C ``traceparent`` string.

    Uses the standard ``TraceContextTextMapPropagator`` so cross-process nesting
    interoperates with any W3C-compliant tracer; returns ``None`` when OTel is
    unavailable.
    """
    if not _OTEL_AVAILABLE:
        return None
    return TraceContextTextMapPropagator().extract({"traceparent": traceparent})


def _resolve_parent(
    parent: Turn | SubAgent | str | None,
) -> tuple[Turn | SubAgent | None, _OTelContext | None, bool]:
    """Resolve ``parent=`` to ``(container, otel_context, force_new_root)``.

    - ``None`` -> the nearest open container (the ambient default).
    - a ``Turn`` / ``SubAgent`` -> that container (explicit override).
    - ``"ignore"`` -> force a brand-new root trace.
    - any other string -> a W3C ``traceparent`` to adopt (cross-process).

    At most one of ``container`` / ``otel_context`` is non-``None``.
    """
    if parent is None:
        return (get_current_span(), None, False)
    if isinstance(parent, (Turn, SubAgent)):
        return (parent, None, False)
    if parent == _IGNORE_PARENT:
        return (None, None, True)
    if isinstance(parent, str):
        return (None, _otel_context_from_traceparent(parent), False)
    raise TypeError(
        f'parent must be a Turn, SubAgent, W3C traceparent string, "{_IGNORE_PARENT}", '
        f"or None; got {type(parent).__name__}"
    )


def start_conversation(
    *,
    agent_name: str = "",
    model: str = "",
    conversation_id: str = "",
    conversation_name: str = "",
    include_content: bool = True,
    continue_parent_trace: bool = False,
    attributes: Attributes = None,
) -> Conversation:
    """Create and activate a conversation. Sets the contextvar for cross-module access.

    ``attributes`` are stamped on every span this conversation emits (e.g. an
    integration identity like ``weave.integration.*``). Use custom,
    non-semconv keys: set semantic-convention fields via the typed params
    (``conversation_name``, ``model``, ...). A key that collides with a span's
    own ``gen_ai.*`` / ``weave.*`` attribute is unsupported; which value
    wins is path-dependent (streaming vs ``log_turn``).
    """
    conversation = Conversation(
        agent_name=agent_name,
        model=model,
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        include_content=include_content,
        continue_parent_trace=continue_parent_trace,
        attributes=attributes or {},
    )
    conversation._token = _current_conversation.set(conversation)
    return conversation


def start_turn(
    *,
    parent: str | None = None,
    user_message: str = "",
    model: str = "",
    agent_name: str = "",
    system_instructions: list[str] | None = None,
) -> Turn:
    """Create and activate a turn. Uses the current conversation if available.

    When a conversation is active, sets the ``_current_turn`` contextvar so the
    turn is visible via ``get_current_turn()`` without a ``with`` block. If no
    conversation is active, returns a disconnected Turn that is NOT set in the
    contextvar (``get_current_turn()`` returns None); enter it with ``with`` to
    activate it.

    ``parent`` accepts a W3C ``traceparent`` string to nest this turn under a
    remote parent span (cross-process); by default each turn starts its own
    trace.
    """
    parent_ctx = (
        _otel_context_from_traceparent(parent)
        if isinstance(parent, str) and parent != _IGNORE_PARENT
        else None
    )
    conversation = get_current_conversation()
    if conversation is not None:
        turn = conversation.start_turn(
            user_message=user_message,
            model=model,
            agent_name=agent_name,
            system_instructions=system_instructions,
        )
        if parent_ctx is not None:
            turn._parent_otel_context = parent_ctx
        # Eager-set on this top-level (imperative) entry point (4c): the object
        # factory ``conversation.start_turn`` no longer sets the contextvar at
        # construction — it's set at ``Turn.__enter__`` so a cross-thread
        # build->enter resets in the entering context — so the imperative
        # no-``with`` contract is satisfied here instead.
        turn._token = _current_turn.set(turn)
        # Push the turn as the current container so its implicit children nest
        # under it. This shadows any active sub-agent from a prior turn for the
        # turn's lifetime (restored on end()) — the container stack replaces the
        # old explicit "drop the sub-agent" step. Mirror of ``Turn.__enter__``.
        turn._container_token = _current_container.set(turn)
        return turn
    turn = Turn(
        agent_name=agent_name,
        model=model,
        system_instructions=system_instructions or [],
    )
    if parent_ctx is not None:
        turn._parent_otel_context = parent_ctx
    if user_message:
        turn.messages.append(Message(role="user", content=user_message))
    return turn


def start_llm(
    *,
    parent: Turn | SubAgent | str | None = None,
    model: str = "",
    provider_name: str = "",
    system_instructions: list[str] | None = None,
) -> LLM:
    """Create and activate an LLM call under the nearest open container.

    Resolves the parent via ``get_current_span()`` — the current sub-agent if
    you're inside one, else the current turn — so an LLM started inside a
    sub-agent nests under the sub-agent, not the turn. When a container is
    active, sets the ``_current_llm`` contextvar so the LLM is visible via
    ``get_current_llm()`` without a ``with`` block. If none is active, returns a
    disconnected LLM (no contextvar set).

    ``parent`` overrides the ambient container: pass a ``Turn`` / ``SubAgent`` to
    nest under it explicitly (e.g. hand one across a thread), a W3C
    ``traceparent`` string to adopt a remote parent (cross-process), or
    ``"ignore"`` to force a brand-new root trace.

    Pass ``provider_name`` explicitly. The SDK does not infer it from the
    model identifier: prefix-based guessing misattributes user fine-tunes
    (e.g. a model named ``text-...``) and bakes assumptions about future
    model names into telemetry that's expensive to correct after the fact.
    """
    container, otel_ctx, force_root = _resolve_parent(parent)
    if container is not None:
        llm = container.start_llm(
            model=model,
            provider_name=provider_name,
            system_instructions=system_instructions,
        )
        # Eager-set for the imperative no-``with`` contract; see ``start_turn``.
        llm._token = _current_llm.set(llm)
        return llm
    llm = LLM(
        model=model,
        provider_name=provider_name,
        system_instructions=system_instructions or [],
    )
    if otel_ctx is not None:
        llm._parent_otel_context = otel_ctx
    llm._force_new_trace = force_root
    return llm


def start_tool(
    *,
    parent: Turn | SubAgent | str | None = None,
    name: str,
    arguments: str = "",
    tool_call_id: str = "",
) -> Tool:
    """Create a tool execution span under the nearest open container.

    Delegates to ``get_current_span()`` (the current sub-agent if inside one,
    else the turn) so the Tool's OTel parent is pinned to that span explicitly —
    it then nests correctly even when entered out-of-block or in another thread,
    matching ``start_llm``. Falls back to a bare Tool (parented via ambient OTel
    context) when no container is active.

    ``parent`` overrides the ambient container (a ``Turn`` / ``SubAgent``, a W3C
    ``traceparent`` string, or ``"ignore"``); see ``start_llm``.
    """
    container, otel_ctx, force_root = _resolve_parent(parent)
    if container is not None:
        tool = container.start_tool(
            name=name, arguments=arguments, tool_call_id=tool_call_id
        )
        # Eager-set for the imperative no-``with`` contract so end_tool() /
        # get_current_tool() work without a block; see ``start_turn``. Tools are
        # leaves, so this contextvar never affects parent resolution.
        tool._token = _current_tool.set(tool)
        return tool
    tool = Tool(name=name, arguments=arguments, tool_call_id=tool_call_id)
    if otel_ctx is not None:
        tool._parent_otel_context = otel_ctx
    tool._force_new_trace = force_root
    return tool


def start_subagent(
    *,
    parent: Turn | SubAgent | str | None = None,
    name: str,
    model: str = "",
    system_instructions: list[str] | None = None,
) -> SubAgent:
    """Create a sub-agent invocation span under the nearest open container.

    Delegates to ``get_current_span()`` (the current sub-agent if inside one —
    enabling agent→agent nesting — else the turn) so the SubAgent's OTel parent
    is pinned explicitly — it then nests correctly even when entered
    out-of-block or in another thread, matching ``start_llm``. Falls back to a
    bare SubAgent (parented via ambient OTel context) when no container is
    active.

    ``parent`` overrides the ambient container (a ``Turn`` / ``SubAgent``, a W3C
    ``traceparent`` string, or ``"ignore"``); see ``start_llm``.
    """
    container, otel_ctx, force_root = _resolve_parent(parent)
    if container is not None:
        sub = container.start_subagent(
            name=name, model=model, system_instructions=system_instructions
        )
        # Eager-set as the current container for the imperative no-``with``
        # contract so end_subagent() / get_current_subagent() work; mirrors
        # ``start_turn``. Restored on the sub-agent's ``end()``.
        sub._container_token = _current_container.set(sub)
        return sub
    sub = SubAgent(
        name=name, model=model, system_instructions=system_instructions or []
    )
    if otel_ctx is not None:
        sub._parent_otel_context = otel_ctx
    sub._force_new_trace = force_root
    return sub


def end_conversation() -> None:
    """End the current conversation (from contextvar)."""
    conversation = get_current_conversation()
    if conversation is not None:
        conversation.end()


def end_turn() -> None:
    """End the current turn (from contextvar)."""
    turn = get_current_turn()
    if turn is not None:
        turn.end()


def end_subagent() -> None:
    """End the current sub-agent (the innermost open one, from the container stack)."""
    subagent = get_current_subagent()
    if subagent is not None:
        subagent.end()


def end_tool() -> None:
    """End the current tool call (from contextvar)."""
    tool = get_current_tool()
    if tool is not None:
        tool.end()


def end_llm() -> None:
    """End the current LLM call (from contextvar)."""
    llm = get_current_llm()
    if llm is not None:
        llm.end()


def get_current_conversation() -> Conversation | None:
    """Return the active conversation from contextvar, or None."""
    return _current_conversation.get()


def get_current_turn() -> Turn | None:
    """Return the active turn from contextvar, or None."""
    return _current_turn.get()


def get_current_span() -> Turn | SubAgent | None:
    """Return the nearest open container — the Turn or SubAgent an implicit
    ``start_llm`` / ``start_tool`` / ``start_subagent`` would nest under, or
    None if none is active.

    This is the single "what's active?" accessor. Turn and SubAgent push
    themselves onto the container stack on ``__enter__`` and pop on ``end()``;
    LLM and Tool are leaves and never appear here.
    """
    return _current_container.get()


def get_current_subagent() -> SubAgent | None:
    """Return the innermost active sub-agent, or None.

    Derived from the container stack (``get_current_span()``): returns the
    current container only when it is a ``SubAgent`` — a ``Turn`` on top means
    no sub-agent is active. Nested sub-agents stack, so this is the innermost.
    Kept for back-compat / introspection; ``get_current_span()`` is the general
    "current parent" accessor.
    """
    container = _current_container.get()
    return container if isinstance(container, SubAgent) else None


def get_current_llm() -> LLM | None:
    """Return the active LLM call from contextvar, or None."""
    return _current_llm.get()


def get_current_tool() -> Tool | None:
    """Return the active tool call from contextvar, or None."""
    return _current_tool.get()


def _to_ns(dt: datetime | None) -> int | None:
    """Convert a datetime to nanoseconds since epoch, or None."""
    return int(dt.timestamp() * 1_000_000_000) if dt is not None else None


def _format_trace_id(trace_id: int) -> str:
    """W3C Trace Context lowercase 32-char hex."""
    return format(trace_id, "032x")


def _format_span_id(span_id: int) -> str:
    """W3C Trace Context lowercase 16-char hex."""
    return format(span_id, "016x")


def _emit_span_now(
    name: str,
    *,
    parent_ctx: Any,
    start_time_ns: int | None,
    end_time_ns: int | None,
    attrs: dict[str, Any],
) -> Any:
    """Emit a fully-formed span without touching contextvars.

    Used by the batch-logging path (``log_turn`` / ``log_conversation``) to
    create children of a parent span without attaching them to the calling
    thread's OTel context. Returns the finished Span so the caller can
    read trace_id / span_id, or None if OTel is unavailable.
    """
    if not _OTEL_AVAILABLE:
        return None
    tracer = otel_trace.get_tracer(_TRACER_NAME)
    kwargs: dict[str, Any] = {}
    if parent_ctx is not None:
        kwargs["context"] = parent_ctx
    if start_time_ns is not None:
        kwargs["start_time"] = start_time_ns
    span = tracer.start_span(name, **kwargs)
    for k, v in attrs.items():
        span.set_attribute(k, v)
    if end_time_ns is not None:
        span.end(end_time=end_time_ns)
    else:
        span.end()
    return span


def _resolve_turn_timestamps(
    *,
    started_at: datetime | None,
    ended_at: datetime | None,
    spans: list[LLM | Tool | SubAgent],
) -> tuple[datetime, datetime]:
    """Pick start/end times for the turn span.

    Prefer explicit ``started_at`` / ``ended_at`` from the caller. Fall back
    to the earliest/latest child timestamps when those are missing. Final
    fallback: ``now()``. Resolved BEFORE constructing the Turn so the
    Turn's ``model_post_init`` doesn't override with ``now()`` first.
    """
    now = datetime.now(timezone.utc)
    starts = [s.started_at for s in spans if s.started_at is not None]
    ends = [s.ended_at for s in spans if s.ended_at is not None]
    return (
        started_at or (min(starts) if starts else now),
        ended_at or (max(ends) if ends else now),
    )


def _attrs_for_span(
    span: LLM | Tool | SubAgent,
    *,
    conversation_id: str,
    conversation_name: str,
    include_content: bool,
) -> tuple[str, dict[str, Any]]:
    """Build (otel_span_name, attribute_dict) for a child span.

    Delegates to each class's ``_build_attrs`` so streaming (``.end()``)
    and batch (``log_turn``) produce byte-identical output.
    """
    if isinstance(span, LLM):
        return f"chat {span.model}", span._build_attrs(
            conversation_id=conversation_id, include_content=include_content
        )
    if isinstance(span, Tool):
        return f"execute_tool {span.name}", span._build_attrs(
            conversation_id=conversation_id, include_content=include_content
        )
    return f"invoke_agent {span.name}", span._build_attrs(
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        include_content=include_content,
    )


def _emit_turn(
    turn: Turn,
    *,
    conversation_id: str,
    conversation_name: str,
    include_content: bool,
    attributes: Attributes = None,
) -> LogResult:
    """Emit one fully-built ``Turn`` (and its child spans) to OTel.

    Shared by ``log_turn`` (which builds the Turn from scalar kwargs) and
    ``log_conversation`` (which is handed Turns directly), so every Turn field —
    ``system_instructions``, ``agent_id`` / ``agent_description`` /
    ``agent_version``, etc. — is honored identically on both batch paths.
    ``continue_parent_trace`` is read from the Turn. Timestamp resolution is
    idempotent when the Turn already carries both timestamps.
    """
    turn_started_at, turn_ended_at = _resolve_turn_timestamps(
        started_at=turn.started_at,
        ended_at=turn.ended_at,
        spans=turn.spans,
    )

    turn_attrs = turn._build_attrs(
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        include_content=include_content,
    )
    if attributes:
        turn_attrs.update(attributes)

    parent_ctx = Context() if not turn.continue_parent_trace else None
    turn_span = _emit_span_now(
        f"invoke_agent {turn.agent_name}",
        parent_ctx=parent_ctx,
        start_time_ns=_to_ns(turn_started_at),
        end_time_ns=_to_ns(turn_ended_at),
        attrs=turn_attrs,
    )
    if turn_span is None:
        return LogResult(conversation_id=conversation_id)

    child_ctx = otel_trace.set_span_in_context(turn_span)
    for child in turn.spans:
        name, attrs = _attrs_for_span(
            child,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            include_content=include_content,
        )
        if attributes:
            attrs.update(attributes)
        _emit_span_now(
            name,
            parent_ctx=child_ctx,
            start_time_ns=_to_ns(child.started_at),
            end_time_ns=_to_ns(child.ended_at),
            attrs=attrs,
        )

    return LogResult(
        conversation_id=conversation_id,
        trace_ids=[_format_trace_id(turn_span.context.trace_id)],
        root_span_ids=[_format_span_id(turn_span.context.span_id)],
        span_count=1 + len(turn.spans),
    )


def log_turn(
    *,
    conversation_id: str,
    agent_name: str = "",
    conversation_name: str = "",
    model: str = "",
    agent_id: str = "",
    agent_description: str = "",
    agent_version: str = "",
    messages: list[Message] | None = None,
    system_instructions: list[str] | None = None,
    spans: list[LLM | Tool | SubAgent] | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    include_content: bool = True,
    continue_parent_trace: bool = False,
    attributes: Attributes = None,
) -> LogResult:
    """Imperatively emit one turn and its child spans to OTel.

    Use when context managers aren't viable (stateless containers, callbacks,
    queue workers). Each child span passed in should have ``started_at`` /
    ``ended_at`` set; the emitted OTel span timestamps come from those fields.
    Falls back to the earliest/latest child timestamp, then ``now()``, when
    the turn doesn't supply its own. ``agent_id`` / ``agent_description`` /
    ``agent_version`` mirror the streaming path.

    ``attributes`` are stamped on every emitted span; the streaming path reads
    these from the active conversation instead. Use custom, non-semconv keys: a
    key that collides with a span's own ``gen_ai.*`` / ``weave.*`` attribute
    is unsupported (which value wins is path-dependent).
    """
    if not _OTEL_AVAILABLE or should_disable_weave():
        return LogResult(conversation_id=conversation_id)

    resolved_spans = spans or []
    # Resolve timestamps before constructing the Turn so model_post_init
    # doesn't override a missing started_at with now() ahead of the
    # earliest-child fallback.
    turn_started_at, turn_ended_at = _resolve_turn_timestamps(
        started_at=started_at,
        ended_at=ended_at,
        spans=resolved_spans,
    )
    turn = Turn(
        agent_name=agent_name,
        model=model,
        agent_id=agent_id,
        agent_description=agent_description,
        agent_version=agent_version,
        system_instructions=system_instructions or [],
        messages=messages or [],
        spans=resolved_spans,
        started_at=turn_started_at,
        ended_at=turn_ended_at,
        continue_parent_trace=continue_parent_trace,
    )
    return _emit_turn(
        turn,
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        include_content=include_content,
        attributes=attributes,
    )


def log_conversation(
    *,
    turns: list[Turn],
    conversation_id: str = "",
    conversation_name: str = "",
    agent_name: str = "",
    model: str = "",
    agent_id: str = "",
    agent_description: str = "",
    agent_version: str = "",
    include_content: bool = True,
    continue_parent_trace: bool = False,
    attributes: Attributes = None,
) -> LogResult:
    """Imperatively emit a complete conversation.

    Each Turn's ``.spans`` attribute provides its children. Auto-generates
    ``conversation_id`` if empty. By default each turn gets its own OTel trace.
    ``agent_name`` / ``model`` / ``agent_id`` / ``agent_description`` /
    ``agent_version`` are conversation-level defaults — a Turn's own value wins;
    the conversation value only fills in when the Turn leaves it empty. The conversation's ``continue_parent_trace`` applies to every turn (a
    per-Turn ``continue_parent_trace`` is intentionally superseded here).

    ``attributes`` are stamped on every emitted span. Use custom, non-semconv
    keys: a key that collides with a span's own ``gen_ai.*`` / ``weave.*``
    attribute is unsupported (which value wins is path-dependent).
    """
    sid = conversation_id or str(uuid.uuid4())
    if not _OTEL_AVAILABLE or should_disable_weave():
        return LogResult(conversation_id=sid)

    trace_ids: list[str] = []
    root_span_ids: list[str] = []
    span_count = 0
    for turn in turns:
        # Emit the caller's Turn directly (every field survives, not just
        # log_turn's kwargs). model_copy applies the conversation defaults (turn
        # wins) + continue_parent_trace without mutating the caller.
        result = _emit_turn(
            turn.model_copy(
                update={
                    "agent_name": turn.agent_name or agent_name,
                    "model": turn.model or model,
                    "agent_id": turn.agent_id or agent_id,
                    "agent_description": turn.agent_description or agent_description,
                    "agent_version": turn.agent_version or agent_version,
                    "continue_parent_trace": continue_parent_trace,
                }
            ),
            conversation_id=sid,
            conversation_name=conversation_name,
            include_content=include_content,
            attributes=attributes,
        )
        trace_ids.extend(result.trace_ids)
        root_span_ids.extend(result.root_span_ids)
        span_count += result.span_count

    return LogResult(
        conversation_id=sid,
        trace_ids=trace_ids,
        root_span_ids=root_span_ids,
        span_count=span_count,
    )
