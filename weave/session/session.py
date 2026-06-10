"""Weave Session SDK — structured logging for agent conversations.

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
from typing_extensions import Self

from weave.session.session_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
    llm_attributes,
)
from weave.session.types import (
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
try:
    from opentelemetry import context as otel_context
    from opentelemetry import trace as otel_trace
    from opentelemetry.context import Context
    from opentelemetry.trace import StatusCode

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

if TYPE_CHECKING:
    from opentelemetry.context import Token as _OTelToken
    from opentelemetry.trace import Span as _OTelSpan


# Re-export types for backwards compatibility with existing imports of
# `weave.session.session.Message` etc. The data classes themselves live
# in `weave.session.types` to break the import cycle with `session_otel`.
__all__ = [
    "LLM",
    "BlobPart",
    "FilePart",
    "LogResult",
    "MediaAttachment",
    "Message",
    "MessagePart",
    "Reasoning",
    "ReasoningPart",
    "Session",
    "SubAgent",
    "TextPart",
    "Tool",
    "ToolCallPart",
    "ToolCallResponsePart",
    "Turn",
    "UriPart",
    "Usage",
    "end_llm",
    "end_session",
    "end_turn",
    "get_current_llm",
    "get_current_session",
    "get_current_turn",
    "log_session",
    "log_turn",
    "start_llm",
    "start_session",
    "start_subagent",
    "start_tool",
    "start_turn",
]


# ---------------------------------------------------------------------------
# Core span classes
# ---------------------------------------------------------------------------


# OTel tracer name — identifies the Session SDK as the source of these spans.
_TRACER_NAME = "weave.session"

logger = logging.getLogger(__name__)


def _capture_info_attrs() -> dict[str, str]:
    """Build weave.* client / system info attrs, gated by settings.

    Per-span (not OTel ``Resource``) so env-var toggles take effect on
    every emit, matching ``@op`` semantics in ``weave_client.py``.
    """
    return {f"weave.{k}": v for k, v in get_capture_info().items()}


class _SpanBase(BaseModel):
    """Shared config for span classes that use ``model`` as a field name."""

    model_config = ConfigDict(protected_namespaces=())

    _otel_span: _OTelSpan | None = PrivateAttr(default=None)
    _otel_token: _OTelToken | None = PrivateAttr(default=None)

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
        """
        if not _OTEL_AVAILABLE or should_disable_weave():
            return
        tracer = otel_trace.get_tracer(_TRACER_NAME)
        kwargs: dict[str, Any] = {}
        if start_time_ns is not None:
            kwargs["start_time"] = start_time_ns
        if new_trace:
            kwargs["context"] = Context()
        self._otel_span = tracer.start_span(name, **kwargs)
        self._otel_token = otel_context.attach(
            otel_trace.set_span_in_context(self._otel_span)
        )

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

    def _check_recording(self, operation: str, key: str | list[str]) -> bool:
        """Return True if the OTel span is recording.

        Else log a warning naming the caller-facing fix. Silent when OTel
        isn't installed or Weave is disabled — both are intentional configs.
        """
        if not _OTEL_AVAILABLE or should_disable_weave():
            return False
        if self._otel_span is None:
            logger.warning(
                "%s(%r) ignored: span not started. Use `with` for live "
                "tracing, or log_turn() for batch ingest.",
                operation,
                key,
            )
            return False
        if not self._otel_span.is_recording():
            logger.warning(
                "%s(%r) ignored: span already ended. Set attributes before "
                "exiting `with` or calling .end().",
                operation,
                key,
            )
            return False
        return True

    def set_attribute(self, key: str, value: Any) -> Self:
        """Stamp an arbitrary OTel attribute on this span.

        Must be called between span start and span end — i.e. inside a
        ``with`` block. Outside that window the call is a no-op and logs
        a warning. For batch ingest, populate the object's declared fields
        directly and pass it to ``log_turn`` / ``log_session``.
        """
        if self._check_recording("set_attribute", key):
            self._otel_span.set_attribute(key, value)
        return self

    def set_attributes(self, attributes: dict[str, Any]) -> Self:
        """Bulk-stamp OTel attributes. Mirrors OTel's ``Span.set_attributes``.

        Convenience over repeated :meth:`set_attribute` when the caller has
        a pre-built dict (e.g. forwarding attributes from an upstream span
        or a transcript replay). Same no-op + warning semantics as
        :meth:`set_attribute`.
        """
        if self._check_recording("set_attributes", list(attributes)):
            self._otel_span.set_attributes(attributes)
        return self

    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> Self:
        """Record an OTel span event at a point in time within this span.

        Examples:
            - ``weave.permission_request`` — record that a permission
              prompt was shown; attributes carry the suggested options
            - Lifecycle markers — ``spawned`` / ``streaming`` / ``finished``
              to time sub-operations inside the span
            - Custom milestones — anything that happens at a point in time
              within the span's lifetime (vs an attribute, which is a
              property of the span as a whole)

        Must be called between span start and span end (inside ``with``).
        Outside that window the call is a no-op and logs a warning.
        """
        if self._check_recording("add_event", name):
            timestamp_ns = (
                int(timestamp.timestamp() * 1_000_000_000) if timestamp else None
            )
            self._otel_span.add_event(
                name, attributes=attributes, timestamp=timestamp_ns
            )
        return self


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

    def _build_attrs(self, *, session_id: str, include_content: bool) -> dict[str, Any]:
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
            conversation_id=session_id,
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

        session = get_current_session()
        attrs = self._build_attrs(
            session_id=session.session_id if session else "",
            include_content=session.include_content if session else True,
        )
        self._end_otel_span(attrs)

    def __enter__(self) -> Self:
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)
        start_ns = int(self.started_at.timestamp() * 1_000_000_000)
        self._start_otel_span(f"execute_tool {self.name}", start_time_ns=start_ns)
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
            name="weave-session-media-upload",
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

    def _build_attrs(self, *, session_id: str, include_content: bool) -> dict[str, Any]:
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
            conversation_id=session_id,
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
        self.ended_at = datetime.now(timezone.utc)

        session = get_current_session()
        attrs = self._build_attrs(
            session_id=session.session_id if session else "",
            include_content=session.include_content if session else True,
        )

        if self._token is not None:
            _current_llm.reset(self._token)
            self._token = None

        self._end_otel_span(attrs)

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_llm.set(self)
        start_ns = (
            int(self.started_at.timestamp() * 1_000_000_000)
            if self.started_at is not None
            else None
        )
        self._start_otel_span(f"chat {self.model}", start_time_ns=start_ns)
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

    def _build_attrs(self, *, session_id: str, session_name: str) -> dict[str, Any]:
        """Build the full OTel attribute dict for this sub-agent span.

        Sub-agents have no content fields — the dispatch only needs
        identifiers and capture-info. Shared between streaming (``end``)
        and batch (``_attrs_for_span``).
        """
        attrs = invoke_agent_attributes(
            agent_name=self.name,
            model=self.model,
            conversation_id=session_id,
            conversation_name=session_name,
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
        self.ended_at = datetime.now(timezone.utc)

        session = get_current_session()
        attrs = self._build_attrs(
            session_id=session.session_id if session else "",
            session_name=session.session_name if session else "",
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
        if exc_val is not None:
            self._record_otel_error(exc_val)
        self.end()
        return False


# ---------------------------------------------------------------------------
# Turn and Session
# ---------------------------------------------------------------------------


class Turn(_SpanBase):
    """One user-agent exchange. Maps to an invoke_agent OTel span.

    By default each turn starts its own OTel trace (``continue_parent_trace=False``)
    so the Agents tab shows one trace per turn. Set ``continue_parent_trace=True``
    on the Session (or directly on the Turn) when an outer trace is already
    active and you want the agent invocation to nest inside it — e.g. inside
    a fastapi-instrumented request.
    """

    agent_name: str = ""
    model: str = ""
    agent_id: str = ""
    agent_description: str = ""
    agent_version: str = ""
    messages: list[Message] = Field(default_factory=list)
    spans: list[LLM | Tool | SubAgent] = Field(default_factory=list)
    continue_parent_trace: bool = False
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

    def _build_attrs(
        self, *, session_id: str, session_name: str, include_content: bool
    ) -> dict[str, Any]:
        """Build the full OTel attribute dict for this turn span.

        Shared by streaming (``end``) and batch (``log_turn``). The Turn
        carries user messages; ``include_content=False`` strips them at
        source so Presidio is never called for already-dropped content.
        """
        messages: list[Message] | None
        if include_content:
            messages = self.messages
            if should_redact_pii():
                messages = pii_redaction.redact_messages(messages)
        else:
            messages = None
        attrs = invoke_agent_attributes(
            agent_name=self.agent_name,
            conversation_id=session_id,
            conversation_name=session_name,
            model=self.model,
            input_messages=messages,
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
        self.ended_at = datetime.now(timezone.utc)

        session = get_current_session()
        attrs = self._build_attrs(
            session_id=session.session_id if session else "",
            session_name=session.session_name if session else "",
            include_content=session.include_content if session else True,
        )

        if self._token is not None:
            _current_turn.reset(self._token)
            self._token = None

        self._end_otel_span(attrs)

    def __enter__(self) -> Self:
        if self._token is None:
            self._token = _current_turn.set(self)
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


class Session(BaseModel):
    """A conversation session. Groups turns by conversation_id (no span).

    ``continue_parent_trace`` controls trace isolation for the turns this
    session creates. Default ``False`` means each turn starts its own OTel
    trace (the right choice for the standalone Agents tab view). Set ``True``
    when the application has an outer trace (e.g. a fastapi-instrumented
    request) that should contain the agent invocation.
    """

    model_config = ConfigDict(protected_namespaces=())

    session_id: str = ""
    session_name: str = ""
    agent_name: str = ""
    model: str = ""
    include_content: bool = True
    continue_parent_trace: bool = False

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
        Propagates ``continue_parent_trace`` from this session.
        """
        if self._current_turn is not None and not self._current_turn._ended:
            self._current_turn.end()
        turn = Turn(
            agent_name=agent_name or self.agent_name,
            model=model or self.model,
            continue_parent_trace=self.continue_parent_trace,
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
    continue_parent_trace: bool = False,
) -> Session:
    """Create and activate a session. Sets the contextvar for cross-module access."""
    session = Session(
        agent_name=agent_name,
        model=model,
        session_id=session_id,
        session_name=session_name,
        include_content=include_content,
        continue_parent_trace=continue_parent_trace,
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

    If no session is active, returns a disconnected Turn that is NOT set
    in the contextvar. This means ``get_current_turn()`` will return None.
    Use ``session.start_turn()`` instead if you need contextvar-based
    cross-module access.
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

    Pass ``provider_name`` explicitly. The SDK does not infer it from the
    model identifier: prefix-based guessing misattributes user fine-tunes
    (e.g. a model named ``text-...``) and bakes assumptions about future
    model names into telemetry that's expensive to correct after the fact.
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


def start_tool(*, name: str, arguments: str = "", tool_call_id: str = "") -> Tool:
    """Create a tool execution span.

    The Tool's OTel span automatically becomes a child of whatever span is
    current in OTel context — typically a Turn span if one is active. No
    explicit turn delegation is needed: parent-child propagation happens
    via OTel context, not via the Session SDK contextvars.
    """
    return Tool(name=name, arguments=arguments, tool_call_id=tool_call_id)


def start_subagent(*, name: str, model: str = "") -> SubAgent:
    """Create a sub-agent invocation span.

    The SubAgent's OTel span automatically becomes a child of whatever span
    is current in OTel context — typically a Turn span if one is active.
    Mirrors ``start_tool`` in shape; OTel context handles parent-child
    propagation, no explicit delegation is needed.
    """
    return SubAgent(name=name, model=model)


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

    Used by the batch-logging path (``log_turn`` / ``log_session``) to
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
    session_id: str,
    session_name: str,
    include_content: bool,
) -> tuple[str, dict[str, Any]]:
    """Build (otel_span_name, attribute_dict) for a child span.

    Delegates to each class's ``_build_attrs`` so streaming (``.end()``)
    and batch (``log_turn``) produce byte-identical output.
    """
    if isinstance(span, LLM):
        return f"chat {span.model}", span._build_attrs(
            session_id=session_id, include_content=include_content
        )
    if isinstance(span, Tool):
        return f"execute_tool {span.name}", span._build_attrs(
            session_id=session_id, include_content=include_content
        )
    return f"invoke_agent {span.name}", span._build_attrs(
        session_id=session_id, session_name=session_name
    )


def log_turn(
    *,
    session_id: str,
    agent_name: str = "",
    session_name: str = "",
    model: str = "",
    messages: list[Message] | None = None,
    spans: list[LLM | Tool | SubAgent] | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    include_content: bool = True,
    continue_parent_trace: bool = False,
) -> LogResult:
    """Imperatively emit one turn and its child spans to OTel.

    Use when context managers aren't viable (stateless containers, callbacks,
    queue workers). Each child span passed in should have ``started_at`` /
    ``ended_at`` set; the emitted OTel span timestamps come from those fields.
    Falls back to the earliest/latest child timestamp, then ``now()``, when
    the turn doesn't supply its own.
    """
    if not _OTEL_AVAILABLE or should_disable_weave():
        return LogResult(session_id=session_id)

    resolved_spans = spans or []
    turn_started_at, turn_ended_at = _resolve_turn_timestamps(
        started_at=started_at,
        ended_at=ended_at,
        spans=resolved_spans,
    )
    turn = Turn(
        agent_name=agent_name,
        model=model,
        messages=messages or [],
        spans=resolved_spans,
        started_at=turn_started_at,
        ended_at=turn_ended_at,
        continue_parent_trace=continue_parent_trace,
    )

    turn_attrs = turn._build_attrs(
        session_id=session_id,
        session_name=session_name,
        include_content=include_content,
    )

    parent_ctx = Context() if not continue_parent_trace else None
    turn_span = _emit_span_now(
        f"invoke_agent {turn.agent_name}",
        parent_ctx=parent_ctx,
        start_time_ns=_to_ns(turn_started_at),
        end_time_ns=_to_ns(turn_ended_at),
        attrs=turn_attrs,
    )
    if turn_span is None:
        return LogResult(session_id=session_id)

    child_ctx = otel_trace.set_span_in_context(turn_span)
    for child in turn.spans:
        name, attrs = _attrs_for_span(
            child,
            session_id=session_id,
            session_name=session_name,
            include_content=include_content,
        )
        _emit_span_now(
            name,
            parent_ctx=child_ctx,
            start_time_ns=_to_ns(child.started_at),
            end_time_ns=_to_ns(child.ended_at),
            attrs=attrs,
        )

    return LogResult(
        session_id=session_id,
        trace_ids=[_format_trace_id(turn_span.context.trace_id)],
        root_span_ids=[_format_span_id(turn_span.context.span_id)],
        span_count=1 + len(turn.spans),
    )


def log_session(
    *,
    turns: list[Turn],
    session_id: str = "",
    session_name: str = "",
    agent_name: str = "",
    model: str = "",
    include_content: bool = True,
    continue_parent_trace: bool = False,
) -> LogResult:
    """Imperatively emit a complete session.

    Each Turn's ``.spans`` attribute provides its children. Auto-generates
    ``session_id`` if empty. By default each turn gets its own OTel trace.
    """
    sid = session_id or str(uuid.uuid4())
    if not _OTEL_AVAILABLE or should_disable_weave():
        return LogResult(session_id=sid)

    trace_ids: list[str] = []
    root_span_ids: list[str] = []
    span_count = 0
    for turn in turns:
        result = log_turn(
            session_id=sid,
            session_name=session_name,
            agent_name=turn.agent_name or agent_name,
            model=turn.model or model,
            messages=turn.messages,
            spans=turn.spans,
            started_at=turn.started_at,
            ended_at=turn.ended_at,
            include_content=include_content,
            continue_parent_trace=continue_parent_trace,
        )
        trace_ids.extend(result.trace_ids)
        root_span_ids.extend(result.root_span_ids)
        span_count += result.span_count

    return LogResult(
        session_id=sid,
        trace_ids=trace_ids,
        root_span_ids=root_span_ids,
        span_count=span_count,
    )
