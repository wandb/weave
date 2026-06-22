"""OTel GenAI export for the OpenAI Realtime integration.

This is the OTel-native sibling of ``state_exporter.StateExporter``. It reuses
*all* of the parent's delta-accumulation machinery — audio buffering, item
threading, per-item timing, transcript gating, and FIFO response ordering —
and overrides only the single export seam (``_emit_response``) so the same
compiled ``inputs`` / ``output_dict`` / ``summary`` are emitted as
OpenTelemetry GenAI spans to Weave's Agents tab instead of legacy Weave calls.

The dispatcher selects this variant when ``WEAVE_USE_OTEL_V2`` is set (the
default), mirroring ``claude_agent_sdk`` and ``openai_agents``. Spans are
created via ``otel_trace.get_tracer(...)`` and ride the global OTel
``TracerProvider`` configured by ``weave.init()`` (``_setup_session_tracing``),
which exports to ``/agents/otel/v1/traces``.

Span tree — one per realtime session:

    invoke_agent {agent_name}     # session root; ended on connection close
    ├── chat {model}              # one per response.done
    │   └── execute_tool {name}   # one per function_call output item
    ├── chat {model}
    └── chat {model}

The realtime API is speech-to-speech: each ``response.done`` is one model
generation, so it maps to one ``chat`` span. Two distinct concerns:

- **Tree grouping** is by the realtime **session** (the websocket connection,
  ``session.id``) — the stable identifier for a whole voice call — so all of a
  session's chat spans nest under one ``invoke_agent`` root in one trace.
- **``gen_ai.conversation.id``** carries the realtime **conversation_id** when
  the API supplies one (the semantically correct conversation identifier),
  falling back to the session id only when it is absent (e.g. Beta).

This path has no notion of legacy Weave "threads" / ``thread_id``.

Audio (user speech in, model speech out) is published as a Weave ``Content``
object and referenced from the message by a ``weave://`` URI ``UriPart``
(plus ``weave.content_refs``), exactly as the Session SDK handles media.
"""

from __future__ import annotations

import datetime
import json
import logging
import threading
from typing import Any

from opentelemetry import trace as otel_trace
from opentelemetry.trace import StatusCode
from pydantic import PrivateAttr

from weave.integrations.integration_metadata import library_integration
from weave.integrations.openai_realtime.encoding import pcm_to_wav
from weave.integrations.openai_realtime.state_exporter import (
    INPUT_AUDIO_TYPE,
    OUTPUT_AUDIO_TYPES,
    SessionSpan,
    StateExporter,
)
from weave.session.agent_context import resolve_agent_name
from weave.session.session_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
    llm_attributes,
)
from weave.session.types import (
    Message,
    TextPart,
    ToolCallPart,
    ToolCallResponsePart,
    UriPart,
    Usage,
)

logger = logging.getLogger(__name__)

_TRACER_NAME = "weave.openai_realtime"
_DEFAULT_AGENT_NAME = "openai_realtime"
_PROVIDER_NAME = "openai"
_AUDIO_MIME_TYPE = "audio/wav"
_AUDIO_MODALITY = "audio"

# Content part types that carry plain text across Beta and GA event shapes.
_TEXT_CONTENT_TYPES = ("text", "input_text", "output_text")

# Integration provenance, flattened once for OTel span attributes (scalars only).
_INTEGRATION_OTEL_ATTRS = library_integration(
    "openai_realtime", distribution_name="openai"
).as_otel_attributes()


def _ns(dt: datetime.datetime | None) -> int | None:
    """Convert a UTC datetime to epoch nanoseconds for OTel span timing.

    Returns None when no timestamp was recorded, letting the OTel SDK fall
    back to the current time at span start/end.
    """
    if dt is None:
        return None
    return int(dt.timestamp() * 1_000_000_000)


def _safe_int(val: Any) -> int | None:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _safe_float(val: Any) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _as_arg_string(val: Any) -> str:
    """Coerce tool-call arguments to a string (semconv wants a JSON string)."""
    if isinstance(val, str):
        return val
    if val is None:
        return ""
    try:
        return json.dumps(val, default=str)
    except (TypeError, ValueError):
        return str(val)


class OTelStateExporter(StateExporter):
    """``StateExporter`` that exports compiled responses as OTel GenAI spans.

    Only the export-time methods are overridden; every event handler that
    accumulates state is inherited unchanged. The two audio-resolution hooks
    (``_resolve_audio`` / ``_extract_audio_content``) are neutralized so the
    compiled payloads keep raw item dicts — this exporter reconstructs audio
    from the parent's buffers and publishes it to ``weave://`` refs itself.
    """

    # group key (session id, else conversation_id, else response_id) -> root span.
    _session_root_spans: dict[str, Any] = PrivateAttr(default_factory=dict)
    # group key -> last activity datetime, used as the root span end time.
    _session_last_activity: dict[str, datetime.datetime] = PrivateAttr(
        default_factory=dict
    )
    # Guards the two maps above; on_exit runs on a different thread than the
    # FIFO completion thread that emits responses.
    _otel_lock: Any = PrivateAttr(default_factory=threading.Lock)

    # ------------------------------------------------------------------
    # Session handlers — store config without creating any Weave calls.
    # ------------------------------------------------------------------
    def _store_session(self, msg: dict) -> None:
        if self.session_span is None:
            # Bare SessionSpan() creates no Weave call (unlike from_session()).
            self.session_span = SessionSpan()
        session = msg.get("session")
        self.session_span.session = session if isinstance(session, dict) else {}

    def handle_session_created(self, msg: dict) -> None:
        self._store_session(msg)

    def handle_session_update(self, msg: dict) -> None:
        self._store_session(msg)

    def handle_session_updated(self, msg: dict) -> None:
        self._store_session(msg)

    def handle_response_created(self, msg: dict) -> None:
        # Record creation timing (used as the chat span start) but do NOT
        # create a conversation call — the OTel root span is created lazily
        # in _emit_response so it can carry semconv attributes.
        self.pending_response = msg.get("response")
        response = self.pending_response or {}
        response_id = response.get("id")
        if response_id:
            self.response_created_at[response_id] = datetime.datetime.now(
                tz=datetime.timezone.utc
            )

    # ------------------------------------------------------------------
    # Audio hooks — neutralized so the compiled payloads stay raw. This
    # exporter pulls audio bytes from the parent buffers and publishes them.
    # ------------------------------------------------------------------
    def _resolve_audio(self, msg: dict) -> Any:
        return msg

    def _extract_audio_content(self, output_list: list[dict], output_dict: dict) -> None:
        return None

    # ------------------------------------------------------------------
    # Audio publishing + message construction
    # ------------------------------------------------------------------
    def _publish_audio(self, pcm_bytes: bytes | None) -> str | None:
        """Publish PCM audio as a WAV ``Content`` and return its ``weave://`` ref.

        Returns None (and logs) on any failure so a publish error degrades to a
        span without the audio ref rather than dropping the whole span.
        """
        if not pcm_bytes:
            return None
        try:
            from weave.trace.api import publish
            from weave.type_wrappers.Content.content import Content

            content = Content.from_bytes(
                pcm_to_wav(bytes(pcm_bytes)), mimetype=_AUDIO_MIME_TYPE
            )
            ref = publish(content)
            # ``ref.uri`` may be a str subclass that OTel attr validation rejects.
            return str(getattr(ref, "uri", ref))
        except Exception:
            logger.exception("openai_realtime OTel: failed to publish audio content")
            return None

    def _content_parts(self, item: dict, refs: list[str]) -> list[Any]:
        """Build message parts for a realtime message item.

        Transcripts become ``TextPart``s; audio is published and referenced via
        ``UriPart``. Any published ref is appended to ``refs`` so the caller can
        populate ``weave.content_refs``.
        """
        item_id = item.get("id")
        parts: list[Any] = []
        for content in item.get("content", []) or []:
            ctype = content.get("type")
            if ctype in _TEXT_CONTENT_TYPES:
                text = content.get("text")
                if text:
                    parts.append(TextPart(content=text))
            elif ctype == INPUT_AUDIO_TYPE:
                transcript = content.get("transcript")
                if transcript:
                    parts.append(TextPart(content=transcript))
                ref = self._publish_audio(
                    self._get_item_audio(item_id) if item_id else None
                )
                if ref:
                    parts.append(
                        UriPart(
                            modality=_AUDIO_MODALITY, mime_type=_AUDIO_MIME_TYPE, uri=ref
                        )
                    )
                    refs.append(ref)
            elif ctype in OUTPUT_AUDIO_TYPES:
                transcript = content.get("transcript")
                if transcript:
                    parts.append(TextPart(content=transcript))
                ref = self._publish_audio(
                    self.response_audio.get(item_id) if item_id else None
                )
                if ref:
                    parts.append(
                        UriPart(
                            modality=_AUDIO_MODALITY, mime_type=_AUDIO_MIME_TYPE, uri=ref
                        )
                    )
                    refs.append(ref)
        return parts

    def _item_to_message(self, item: dict, refs: list[str]) -> Message | None:
        """Convert one realtime conversation item into a session ``Message``."""
        itype = item.get("type")
        if itype == "function_call":
            call_id = item.get("call_id") or item.get("id") or ""
            return Message(
                role="assistant",
                parts=[
                    ToolCallPart(
                        id=call_id,
                        name=item.get("name", ""),
                        arguments=_as_arg_string(item.get("arguments")),
                    )
                ],
            )
        if itype == "function_call_output":
            call_id = item.get("call_id") or item.get("id") or ""
            return Message(
                role="tool",
                parts=[ToolCallResponsePart(id=call_id, response=item.get("output", ""))],
            )
        if itype == "message":
            role = item.get("role") or "user"
            parts = self._content_parts(item, refs)
            if parts:
                return Message(role=role, parts=parts)
            return Message(role=role, content="")
        return None

    def _build_usage(self, output_dict: dict) -> Usage | None:
        """Map the realtime response usage block onto a session ``Usage``."""
        usage = output_dict.get("usage")
        if not isinstance(usage, dict):
            return None
        input_details = usage.get("input_token_details")
        cached = 0
        if isinstance(input_details, dict):
            cached = _safe_int(input_details.get("cached_tokens")) or 0
        return Usage(
            input_tokens=_safe_int(usage.get("input_tokens")) or 0,
            output_tokens=_safe_int(usage.get("output_tokens")) or 0,
            cache_read_input_tokens=cached,
        )

    # ------------------------------------------------------------------
    # Span lifecycle
    # ------------------------------------------------------------------
    def _ensure_session_root(
        self,
        tracer: Any,
        group_key: str,
        conversation_id: str,
        model: str,
        created_at: datetime.datetime | None,
    ) -> Any:
        """Return the open ``invoke_agent`` root span for a realtime session.

        Created lazily on the first response and held open until the connection
        closes (``on_exit``), so every ``chat`` of the session nests under one
        root (``group_key`` is the session-scoped grouping key). The root's
        ``gen_ai.conversation.id`` is the realtime conversation_id when
        available, established from the first response of the session.
        """
        with self._otel_lock:
            existing = self._session_root_spans.get(group_key)
            if existing is not None:
                return existing
            agent_name = resolve_agent_name(_DEFAULT_AGENT_NAME)
            attrs = invoke_agent_attributes(
                agent_name=agent_name,
                conversation_id=conversation_id,
                provider_name=_PROVIDER_NAME,
                model=model,
            )
            attrs.update(_INTEGRATION_OTEL_ATTRS)
            root = tracer.start_span(
                f"invoke_agent {agent_name}".rstrip(), start_time=_ns(created_at)
            )
            for key, value in attrs.items():
                root.set_attribute(key, value)
            self._session_root_spans[group_key] = root
            if created_at:
                self._session_last_activity[group_key] = created_at
            return root

    def _emit_response(
        self,
        *,
        response: dict,
        conv_id: str | None,
        response_id: str | None,
        inputs: dict[str, Any],
        output_dict: dict[str, Any],
        summary: dict[str, Any],
        created_at: datetime.datetime | None,
        done_at: datetime.datetime | None,
        first_content_at: datetime.datetime | None,
    ) -> None:
        # Never let span bookkeeping break the FIFO completion thread.
        try:
            self._emit_otel(
                response=response,
                conv_id=conv_id,
                response_id=response_id,
                inputs=inputs,
                output_dict=output_dict,
                created_at=created_at,
                done_at=done_at,
                first_content_at=first_content_at,
            )
        except Exception:
            logger.exception(
                "openai_realtime OTel export failed for response %s", response_id
            )

    def _emit_otel(
        self,
        *,
        response: dict,
        conv_id: str | None,
        response_id: str | None,
        inputs: dict[str, Any],
        output_dict: dict[str, Any],
        created_at: datetime.datetime | None,
        done_at: datetime.datetime | None,
        first_content_at: datetime.datetime | None,
    ) -> None:
        tracer = otel_trace.get_tracer(_TRACER_NAME)
        session = self.session_span.get_session() if self.session_span else None
        model = (session or {}).get("model") or "unknown"

        # gen_ai.conversation.id priority (semantic-convention first):
        #   1. realtime conversation_id  — the spec-correct conversation id, and
        #      what lands in the `conversation_id` column the agents tab groups on
        #   2. realtime session id       — fallback only. The `spans` table has
        #      `conversation_id` + `conversation_name` but NO dedicated session
        #      column (verified against the schema), so the session id has no
        #      other home; it backstops conversation_id when the API omits one
        #      (e.g. Beta).
        # Tree grouping is independent: the span tree is always rooted per
        # SESSION (the websocket call) so the whole voice call is one trace,
        # regardless of which value ends up in conversation.id.
        session_id = (session or {}).get("id") or ""
        group_key = session_id or conv_id or response_id or "default"
        conversation_id = conv_id or session_id or ""

        root = self._ensure_session_root(
            tracer, group_key, conversation_id, model, created_at
        )

        refs: list[str] = []

        # Input messages: the prior conversation thread feeding this response.
        input_messages: list[Message] = []
        for item in inputs.get("messages", []) or []:
            msg = self._item_to_message(item, refs)
            if msg is not None:
                input_messages.append(msg)

        # Output: assemble one assistant message (text + audio + tool-call parts)
        # and collect function_call items for execute_tool child spans.
        out_parts: list[Any] = []
        tool_call_items: list[dict] = []
        has_audio = False
        for out_item in output_dict.get("output", []) or []:
            otype = out_item.get("type")
            if otype == "message":
                before = len(refs)
                out_parts.extend(self._content_parts(out_item, refs))
                if len(refs) > before:
                    has_audio = True
            elif otype == "function_call":
                call_id = out_item.get("call_id") or out_item.get("id") or ""
                out_parts.append(
                    ToolCallPart(
                        id=call_id,
                        name=out_item.get("name", ""),
                        arguments=_as_arg_string(out_item.get("arguments")),
                    )
                )
                tool_call_items.append(out_item)
        output_messages = [Message(role="assistant", parts=out_parts)] if out_parts else []

        attrs = llm_attributes(
            model=model,
            provider_name=_PROVIDER_NAME,
            conversation_id=conversation_id,
            input_messages=input_messages or None,
            output_messages=output_messages or None,
            usage=self._build_usage(output_dict),
            response_id=response_id or "",
            response_model=model,
            output_type="speech" if has_audio else "text",
            request_temperature=_safe_float((session or {}).get("temperature")),
            request_max_tokens=_safe_int(
                (session or {}).get("max_response_output_tokens")
            ),
        )
        attrs.update(_INTEGRATION_OTEL_ATTRS)
        if refs:
            attrs["weave.content_refs"] = [str(r) for r in refs]

        chat_ctx = otel_trace.set_span_in_context(root)
        chat = tracer.start_span(
            f"chat {model}".rstrip(), context=chat_ctx, start_time=_ns(created_at)
        )
        for key, value in attrs.items():
            chat.set_attribute(key, value)
        if response.get("status") == "failed":
            details = response.get("status_details")
            err = details.get("error") if isinstance(details, dict) else None
            message = (
                err.get("message") if isinstance(err, dict) else None
            ) or "response failed"
            chat.set_status(StatusCode.ERROR, str(message))

        # execute_tool children, parented under the chat span.
        tool_parent_ctx = otel_trace.set_span_in_context(chat)
        for fc in tool_call_items:
            self._emit_tool_span(
                tracer, tool_parent_ctx, fc, conversation_id, created_at, done_at
            )

        chat.end(end_time=_ns(done_at) or _ns(first_content_at))

        if done_at:
            with self._otel_lock:
                self._session_last_activity[group_key] = done_at

    def _emit_tool_span(
        self,
        tracer: Any,
        parent_ctx: Any,
        fc: dict,
        conversation_id: str,
        created_at: datetime.datetime | None,
        done_at: datetime.datetime | None,
    ) -> None:
        item_id = fc.get("id")
        ts = self.item_timestamps.get(item_id, {}) if item_id else {}
        start = ts.get("started") or created_at
        end = ts.get("completed") or done_at
        name = fc.get("name", "")
        attrs = execute_tool_attributes(
            tool_name=name,
            conversation_id=conversation_id,
            tool_call_id=fc.get("call_id") or fc.get("id") or "",
            tool_call_arguments=_as_arg_string(fc.get("arguments")),
        )
        attrs.update(_INTEGRATION_OTEL_ATTRS)
        tool_span = tracer.start_span(
            f"execute_tool {name}".rstrip(), context=parent_ctx, start_time=_ns(start)
        )
        for key, value in attrs.items():
            tool_span.set_attribute(key, value)
        tool_span.end(end_time=_ns(end))

    def on_exit(self) -> None:
        """End all open session root spans on connection close."""
        with self._otel_lock:
            spans = list(self._session_root_spans.items())
            last = dict(self._session_last_activity)
            self._session_root_spans.clear()
            self._session_last_activity.clear()
        for group_key, root in spans:
            try:
                root.end(end_time=_ns(last.get(group_key)))
            except Exception:
                logger.exception(
                    "openai_realtime OTel: failed to end session root span"
                )
