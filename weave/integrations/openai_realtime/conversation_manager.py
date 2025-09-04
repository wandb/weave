from __future__ import annotations

import asyncio
from threading import Lock
from typing import Optional, Union, cast, Callable, TypeVar, Type
import threading
import time
import logging

from pydantic import BaseModel, Field

from weave.integrations.openai_realtime import models
from weave.integrations.openai_realtime.encoding import pcm_to_wav
from weave.type_wrappers.Content import Content
from weave.integrations.openai_realtime.state_manager import CustomInputContext, StateStore, StoredItem, TimelineContext
from weave.trace.weave_client import Call

logger = logging.getLogger(__name__)



class TurnRecord(BaseModel):
    """Tracks a single turn keyed by response_id."""

    response_id: Optional[models.ResponseID] = None
    created_at: float = Field(default_factory=lambda: time.time())
    user_context: Optional[Union[TimelineContext, CustomInputContext]] = None
    assistant_context: Optional[TimelineContext] = None
    inputs_complete: bool = False
    response_done: bool = False
    index: int = 0
    # Internal: we saw a user 'response.create' for this turn before server 'response.created'
    saw_response_create: bool = False


T_specific = TypeVar("T_specific", bound=models.MessageType)

# Use a uniform handler type for registry storage. We adapt
# specific handlers (expecting concrete message classes) into this.
Handler = Callable[[models.MessageType], None]

def adapt_handler(cls: Type[T_specific], func: Callable[[T_specific], None]) -> Handler:
    """Adapt a concrete-typed handler into a generic registry handler.

    This preserves runtime safety (checks isinstance before calling) and
    side-steps contravariance issues that Pyright flagged for a heterogeneous
    handler map.
    """
    def _wrapped(msg: models.MessageType) -> None:
        if isinstance(msg, cls):
            func(cast(T_specific, msg))
        else:
            return
    return _wrapped


class EventHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type] = handler

    def update(
        self, handlers: dict[str, Handler]
    ) -> None:
        for event, handler in handlers.items():
            self.register(event, handler)

    def get(self, event_type: str) -> Optional[Handler]:
        return self._handlers.get(event_type)

class ConversationManager:
    """
    Orchestrates event-driven state management for a conversation.
    Provides async queue submission and direct processing.
    """

    def __init__(self) -> None:
        self.state = StateStore()
        self._registry = EventHandlerRegistry()
        self._queue: asyncio.Queue[models.MessageType] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = Lock()

        handlers: dict[str, Handler] = {
            "session.created": adapt_handler(models.SessionCreatedMessage, self.state.apply_session_created),
            "session.updated": adapt_handler(models.SessionUpdatedMessage, self.state.apply_session_updated),

            # Input audio buffer lifecycle
            "input_audio_buffer.append": adapt_handler(models.InputAudioBufferAppendMessage, self.state.apply_input_audio_append),
            "input_audio_buffer.cleared": adapt_handler(models.InputAudioBufferClearedMessage, self.state.apply_input_audio_cleared),
            "input_audio_buffer.committed": adapt_handler(models.InputAudioBufferCommittedMessage, self.state.apply_input_audio_committed),
            "input_audio_buffer.speech_started": adapt_handler(models.InputAudioBufferSpeechStartedMessage, self.state.apply_speech_started),
            "input_audio_buffer.speech_stopped": adapt_handler(models.InputAudioBufferSpeechStoppedMessage, self.state.apply_speech_stopped),

            # Conversation item changes
            # Unused "conversation.item.create": self._handle_item_create,
            "conversation.item.created": adapt_handler(models.ItemCreatedMessage, self.state.apply_item_created),
            "conversation.item.truncated": adapt_handler(models.ItemTruncatedMessage, self.state.apply_item_truncated),
            "conversation.item.deleted": adapt_handler(models.ItemDeletedMessage, self.state.apply_item_deleted),
            "conversation.item.input_audio_transcription.delta": adapt_handler(models.ItemInputAudioTranscriptionDeltaMessage, self.state.apply_item_input_audio_transcription_delta),
            "conversation.item.input_audio_transcription.completed": adapt_handler(models.ItemInputAudioTranscriptionCompletedMessage, self.state.apply_item_input_audio_transcription_completed),

            # Response lifecycle and parts
            "response.create": adapt_handler(models.ResponseCreateMessage, self._handle_response_create),
            "response.created": adapt_handler(models.ResponseCreatedMessage, self._handle_response_created),
            "response.cancel": adapt_handler(models.ResponseCancelMessage, self._handle_response_cancel),
            "response.done": adapt_handler(models.ResponseDoneMessage, self._handle_response_done),
            "response.output_item.added": adapt_handler(models.ResponseOutputItemAddedMessage, self.state.apply_response_output_item_added),
            "response.output_item.done": adapt_handler(models.ResponseOutputItemDoneMessage, self.state.apply_response_output_item_done),
            "response.content_part.added": adapt_handler(models.ResponseContentPartAddedMessage, self.state.apply_response_content_part_added),
            "response.content_part.done": adapt_handler(models.ResponseContentPartDoneMessage, self.state.apply_response_content_part_done),
            "response.text.delta": adapt_handler(models.ResponseTextDeltaMessage, self.state.apply_response_text_delta),
            "response.text.done": adapt_handler(models.ResponseTextDoneMessage, self.state.apply_response_text_done),
            "response.audio_transcript.delta": adapt_handler(models.ResponseAudioTranscriptDeltaMessage, self.state.apply_response_audio_transcript_delta),
            "response.audio_transcript.done": adapt_handler(models.ResponseAudioTranscriptDoneMessage, self.state.apply_response_audio_transcript_done),
            "response.audio.delta": adapt_handler(models.ResponseAudioDeltaMessage, self.state.apply_response_audio_delta),
            "response.audio.done": adapt_handler(models.ResponseAudioDoneMessage, self._handle_response_audio_done),
            "response.function_call_arguments.delta": adapt_handler(models.ResponseFunctionCallArgumentsDeltaMessage, self.state.apply_response_function_call_arguments_delta),
            "response.function_call_arguments.done": adapt_handler(models.ResponseFunctionCallArgumentsDoneMessage, self.state.apply_response_function_call_arguments_done),
            # Error handling
            "error": adapt_handler(models.ErrorMessage, self._handle_error),
            # Rate limits
            "rate_limits.updated": adapt_handler(models.RateLimitsUpdatedMessage, self._handle_rate_limits_updated),
        }
        self._registry.update(handlers)

        # Turn tracking
        self._turn_counter = 0
        self._pending_create_queue: list[TurnRecord] = []
        self._turns_by_response: dict[models.ResponseID, TurnRecord] = {}
        self._debounce_timers: dict[models.ResponseID, threading.Timer] = {}
        self.turn_export_dir: Optional[str] = None  # if set, export completed turns here
        # Export numbering (contiguous across exported turns only)
        self._export_counter: int = 0
        # Populated by connection wrappers if available
        self.client_base_url: Optional[str] = None
        # Track weave call objects per response to finish later
        self._weave_calls: dict[models.ResponseID, Call] = {}

    async def start(self) -> None:
        logger.debug("ConversationManager.start: starting worker task")
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    async def submit_event(self, event: models.MessageType) -> None:
        await self._queue.put(event)

    def process_event(self, event: models.MessageType) -> None:
        """Process an event synchronously (useful for tests or simple flows)."""
        # Event objects have a 'type' field in pydantic models.
        event_type = getattr(event, "type", None)
        if not event_type:
            return

        handler = self._registry.get(event_type)
        if handler:
            with self._lock:
                handler(event)
                # After every event, opportunistically check any pending input completions
                self._maybe_check_all_turns()

    def get_conversation_history(self) -> list[StoredItem]:
        return [it for it in self.state.get_conversation_history()]

    def get_item(self, item_id: models.ItemID) -> Optional[StoredItem]:
        return self.state.items.get(item_id)


    def get_audio_segment(self, item_id: models.ItemID) -> Optional[bytes]:
        return self.state.get_audio_segment(item_id)

    def _get_response_for_item(self, item_id: models.ItemID) -> Optional[models.ResponseID]:
        return self.state.get_response_for_item(item_id)

    # Formatting helpers
    def _format_content_part(
        self,
        part: object,
        *,
        item_id: Optional[models.ItemID] = None,
        response_id: Optional[models.ResponseID] = None,
        content_index: Optional[int] = None,
    ) -> Optional[dict[str, object]]:
        """Normalize an item content part to a stable schema.

        Returns a dict shaped as one of:
        - {"type": "text", "text": str}
        - {"type": "audio", "audio": {"transcript": str, "data": Content|None, "format": str}}

        Unknown/unsupported parts return None.
        """
        ptype = getattr(part, "type", None)

        # Text-like parts
        if ptype in ("input_text", "text"):
            text = getattr(part, "text", None)
            if text is None:
                return None
            return {"type": "text", "text": text}

        # User input audio
        if ptype == "input_audio":
            # Prefer the transcript stored on the part, fall back to accumulated transcripts
            transcript = getattr(part, "transcript", None)
            if transcript is None and item_id is not None:
                # attempt to reconstruct from state if present
                # We don't know content_index for user items reliably here, so best-effort only
                pass
            # Encode the PCM slice for the full spoken span of this item if available
            data: Optional[Content] = None
            if item_id is not None:
                try:
                    seg = self.get_audio_segment(item_id)
                    if seg:
                        data = Content.from_bytes(pcm_to_wav(seg), extension=".wav")
                except Exception:
                    data = None
            return {
                "type": "audio",
                "audio": {
                    "transcript": transcript or "",
                    "data": data,
                    "format": "audio/wav",
                },
            }

        # Assistant output audio
        if ptype == "audio":
            transcript = getattr(part, "transcript", None) or ""
            data: Optional[Content] = None
            if response_id is not None and item_id is not None and content_index is not None:
                try:
                    buf = self.state.resp_audio_bytes.get((response_id, item_id, content_index))
                    if buf:
                        data = Content.from_bytes(pcm_to_wav(bytes(buf)), extension=".wav")
                except Exception:
                    data = None
            return {
                "type": "audio",
                "audio": {
                    "transcript": transcript,
                    "data": data,
                    "format": 'audio/wav',
                },
            }

        return None

    def _format_item(
        self,
        item: object,
        *,
        response_id: Optional[models.ResponseID] = None,
    ) -> Optional[dict[str, object]]:
        """Format any conversation or response item into a single message-like object.

        - Message items -> {role, content: [mapped parts]}
        - Function call -> assistant tool_calls envelope
        - Function call output -> tool role message
        """
        # The function call instance check fails so just use this
        if getattr(item, "type", None) == "function_call":
             return {
                 "role": "assistant",
                 "content": None,
                 "refusal": None,
                 "annotations": [],
                 "function_call": None,
                 "tool_calls": [
                     {
                         "id": getattr(item, "call_id", None),
                         "type": "function",
                         "function": {
                             "name": getattr(item, "name", None),
                             "arguments": getattr(item, "arguments", None),
                         },
                     }
                 ],
             }

        if getattr(item, "type", None) == "function_call_output":
            call_id = getattr(item, "call_id", None)
            name = None
            for other in self.state.items.values():
                if getattr(other, "type", None) == "function_call" and getattr(other, "call_id", None) == call_id:
                    name = getattr(other, "name", None)
                    break

                return {
                    "role": "tool",
                    "content": getattr(item, "output", None),
                    "tool_call_id": call_id,
                    "name": name,
                }
        # System message
        if isinstance(item, (models.ClientSystemMessageItem, models.ServerSystemMessageItem)):
            parts: list[dict[str, object]] = []
            for idx, p in enumerate(getattr(item, "content", []) or []):
                out = self._format_content_part(p, item_id=getattr(item, "id", None), content_index=idx)
                if out is not None:
                    parts.append(out)
            return {"role": "system", "content": parts}

        # User message
        if isinstance(item, (models.ClientUserMessageItem, models.ServerUserMessageItem)):
            parts: list[dict[str, object]] = []
            iid = getattr(item, "id", None)
            for idx, p in enumerate(getattr(item, "content", []) or []):
                out = self._format_content_part(p, item_id=iid, content_index=idx)
                if out is not None:
                    parts.append(out)
            return {"role": "user", "content": parts}

        # Assistant message (may appear as server message or response item)
        if isinstance(item, (models.ClientAssistantMessageItem, models.ServerAssistantMessageItem, models.ResponseMessageItem)):
            parts: list[dict[str, object]] = []
            iid = getattr(item, "id", None)
            for idx, p in enumerate(getattr(item, "content", []) or []):
                out = self._format_content_part(p, item_id=iid, response_id=response_id, content_index=idx)
                if out is not None:
                    parts.append(out)
            return {
                "role": "assistant",
                "content": parts,
                "refusal": None,
                "annotations": [],
                "function_call": None,
                "tool_calls": None,
            }

        return None

    def _get_or_create_turn_for_created(self, resp_id: models.ResponseID) -> TurnRecord:
        # Bind the earliest pending create to this response
        if self._pending_create_queue:
            rec = self._pending_create_queue.pop(0)
        else:
            rec = TurnRecord()
        rec.response_id = resp_id
        # Attach captured context snapshot if available
        ctx = self.state.response_context.get(resp_id)
        if ctx:
            rec.user_context = ctx.get("user_context")
            rec.assistant_context = ctx.get("assistant_context")
        self._turn_counter += 1
        rec.index = self._turn_counter
        self._turns_by_response[resp_id] = rec
        return rec

    def _ensure_turn_for_resp(self, resp_id: models.ResponseID) -> Optional[TurnRecord]:
        rec = self._turns_by_response.get(resp_id)
        if rec is None:
            rec = self._get_or_create_turn_for_created(resp_id)
        return rec

    def _collect_input_item_ids(self, rec: TurnRecord) -> list[models.ItemID]:
        # Prefer assistant_context timeline as full context snapshot
        if rec.assistant_context and isinstance(rec.assistant_context, dict) and "timeline_items" in rec.assistant_context:
            return list(cast(TimelineContext, rec.assistant_context)["timeline_items"])  # type: ignore[index]
        if rec.user_context and isinstance(rec.user_context, dict) and "timeline_items" in rec.user_context:
            return list(cast(TimelineContext, rec.user_context)["timeline_items"])  # type: ignore[index]
        # No timeline-based context; fall back to current timeline
        return list(self.state.timeline)

    def _inputs_complete_for_turn(self, rec: TurnRecord) -> bool:
        # Accept both client-initiated turns (response.create) and
        # server-initiated turns (e.g., VAD-created). We no longer
        # require that a response.create was seen for inputs to be
        # considered complete.

        # Resolve items considered part of inputs
        item_ids = self._collect_input_item_ids(rec)

        # Rule 1: nothing with status == in_progress among input items (defensive)
        for iid in item_ids:
            it = self.state.items.get(iid)
            if it is None:
                continue
            st = getattr(it, "status", None)
            if st == "in_progress":
                return False

        # Determine if transcripts are required
        transcripts_required = bool(self.state.session and self.state.session.input_audio_transcription)

        # Gather checks for audio/transcripts
        for iid in item_ids:
            it = self.state.items.get(iid)
            if not isinstance(it, (models.ServerUserMessageItem,)):
                continue
            # Check each content part
            for part in getattr(it, "content", []) or []:
                if isinstance(part, models.InputAudioContentPart):
                    # Rule 3: corresponding item must be committed
                    if iid not in self.state.committed_item_ids:
                        return False
                    # Rule 2: transcripts present if required
                    if transcripts_required and not part.transcript:
                        return False
        return True

    def _maybe_check_all_turns(self) -> None:
        # Iterate through known turns and update inputs_complete flags
        for rec in list(self._turns_by_response.values()):
            if not rec.inputs_complete and self._inputs_complete_for_turn(rec):
                rec.inputs_complete = True
                self._on_client_complete(rec)

    def _on_client_complete(self, _rec: TurnRecord) -> None:
        logger.debug("_on_client_complete: inputs complete for response")
        # Once inputs for a turn are completed, create a weave call for this turn
        # using the same formatted inputs as the export function.
        rec = _rec
        if not rec.response_id:
            logger.warning("_on_client_complete: missing response_id; cannot create call")
            return
        # Avoid creating duplicate calls
        if rec.response_id in self._weave_calls:
            logger.debug("_on_client_complete: call already exists for response_id=%s", rec.response_id)
            return
        # Ensure we have a session id to bind the thread context
        sess = self.state.session
        if not sess:
            logger.warning("_on_client_complete: no session; skipping trace creation")
            return
        try:
            import weave  # local import to avoid hard dependency at module import time
            # Acquire client from context within a thread tied to the session id
            with weave.thread(sess.id):
                from weave.trace.context.weave_client_context import get_weave_client
                client = get_weave_client()
                if not client:
                    logger.warning("_on_client_complete: no weave client in context; skipping")
                    return
                # Build inputs matching export formatting
                inputs = self._build_inputs_payload(rec)
                # Use the op name conversation_turn, like sessions.py
                call = client.create_call(op="conversation_turn", inputs=inputs)
                self._weave_calls[rec.response_id] = call
                # If the response already finished, finish immediately here
                if rec.response_done:
                    outputs = self._build_output_payload(rec)
                    client.finish_call(call, output=outputs)
        except Exception as e:
            logger.error(f"Error submitting trace in _on_client_complete - {e}")
            # Never let tracing interfere with core flow
            return

    def _build_inputs_payload(self, rec: TurnRecord) -> dict[str, object]:
        """Build Inputs payload matching the requested schema."""
        sess = self.state.session
        item_ids = self._collect_input_item_ids(rec)

        # Helper: response_id for an assistant message item
        def _response_id_for_item(iid: models.ItemID) -> Optional[models.ResponseID]:
            return self._get_response_for_item(iid)

        messages: list[dict[str, object]] = []

        for iid in item_ids:
            it = self.state.items.get(iid)
            if it is None:
                continue
            rid = _response_id_for_item(iid)
            formatted = self._format_item(it, response_id=rid)
            if formatted is None:
                continue
            role = formatted.get("role")
            if role == "system":
                # Preserve original behavior: collapse to a single string
                parts_obj = formatted.get("content")
                texts: list[str] = []
                if isinstance(parts_obj, list):
                    for p in parts_obj:
                        if isinstance(p, dict):
                            t = p.get("text")
                            if p.get("type") == "text" and isinstance(t, str) and t:
                                texts.append(t)
                messages.append({"role": "system", "content": "\n".join(texts) if texts else ""})
            elif role == "assistant" and formatted.get("tool_calls") is None:
                # Preserve original behavior: only include audio parts for assistant context
                parts_obj = formatted.get("content")
                audio_parts: Optional[list[dict[str, object]]] = None
                if isinstance(parts_obj, list):
                    audio_list = [p for p in parts_obj if isinstance(p, dict) and p.get("type") == "audio"]
                    audio_parts = audio_list or None
                messages.append({
                    "role": "assistant",
                    "content": audio_parts or None,
                    "refusal": None,
                    "annotations": [],
                    "function_call": None,
                    "tool_calls": None,
                })
            else:
                messages.append(formatted)

        # Normalize tool_choice for JSON
        tool_choice_val: object
        if sess and sess.tool_choice is not None:
            tc = sess.tool_choice
            try:
                # Pydantic BaseModel
                tool_choice_val = tc.model_dump()  # type: ignore[attr-defined]
            except Exception:
                tool_choice_val = tc  # likely a string literal
        else:
            tool_choice_val = "auto"

        return {
            "self": {
                "client": {
                    "base_url": self.client_base_url or "",
                    "version": "1.0.0",
                }
            },
            "messages": messages,
            "model": (sess.model if sess else None) or "gpt-4o-realtime",
            "tools": (sess.tools if sess and sess.tools is not None else []),
            "tool_choice": tool_choice_val,
            "audio": {
                "voice": (sess.voice if sess else "alloy"),
                "format": (sess.output_audio_format if sess else "pcm16"),
            },
            "modalities": list(sess.modalities) if sess and sess.modalities is not None else ["audio", "text"],
        }

    def _build_output_payload(self, rec: TurnRecord) -> dict[str, object]:
        """Build Output payload matching the requested schema."""
        if not rec.response_id:
            logger.warning("_build_output_payload: missing response_id; returning empty payload")
            return {}
        resp = self.state.get_response(rec.response_id)
        if not resp:
            logger.warning("_build_output_payload: response not found for response_id=%s", rec.response_id)
            return {}

        sess = self.state.session

        # Build assistant message by formatting the first assistant ResponseMessageItem
        assistant_message: dict[str, object] = {"role": "assistant", "content": []}
        for it in resp.output:
            if isinstance(it, models.ResponseMessageItem) and getattr(it, "role", None) == "assistant":
                fmt = self._format_item(it, response_id=resp.id)
                if fmt is not None:
                    assistant_message = fmt
                break

        usage_obj: Optional[dict[str, object]] = None
        if resp.usage is not None:
            u = resp.usage
            usage_obj = {
                "total_tokens": u.total_tokens,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "input_token_details": (u.input_token_details.model_dump() if u.input_token_details else None),
                "output_token_details": (u.output_token_details.model_dump() if u.output_token_details else None),
            }

        return {
            "id": resp.id,
            "model": (sess.model if sess else None) or "gpt-4o-realtime",
            "status": resp.status,
            "status_details": resp.status_details,
            "object": "chat.completion",
            "usage": usage_obj,
            "choices": [
                {
                    "index": 0,
                    "message": assistant_message,
                    "finish_reason": "stop",
                }
            ],
        }

    async def _worker(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                self.process_event(event)
            finally:
                self._queue.task_done()

    def _build_message_input_payload(self, item_id: models.ItemID) -> dict[str, object]:
        """
        Format a single stored item into a message object with all parts mapped.
        """
        it = self.state.items.get(item_id)
        if it is None:
            return {}
        rid = self._get_response_for_item(item_id)
        msg = self._format_item(it, response_id=rid)
        return msg or {}

    

    def _build_message_output_payload(
        self,
        item: models.ResponseMessageItem,
        response_id: models.ResponseID,
    ) -> dict[str, object]:
        """Format a single assistant response message into a message object."""
        msg = self._format_item(item, response_id=response_id)
        return msg or {}

    

    # Responses
    def _handle_response_create(self, msg: models.ResponseCreateMessage) -> None:
        # Delegate state bookkeeping; record a pending turn awaiting server response.created
        self.state.apply_response_create(msg)
        tr = TurnRecord(saw_response_create=True)
        self._pending_create_queue.append(tr)

    def _handle_response_created(self, msg: models.ResponseCreatedMessage) -> None:
        self.state.apply_response_created(msg)
        # Bind to a TurnRecord
        rec = self._get_or_create_turn_for_created(msg.response.id)
        # If a pending create existed earlier, preserve that flag
        if not rec.saw_response_create and self._pending_create_queue:
            # Already handled above, so nothing here
            pass

    def _handle_response_cancel(self, msg: models.ResponseCancelMessage) -> None:
        # This is just the client cancellation message
        ...

    def _handle_response_done(self, msg: models.ResponseDoneMessage) -> None:
        self.state.apply_response_done(msg)
        # Mark output complete for this turn and handle export logic
        rec = self._ensure_turn_for_resp(msg.response.id)
        if not rec:
            logger.warning("_handle_response_done: missing TurnRecord for response_id=%s", msg.response.id)
            return
        rec.response_done = True
        self._handle_turn_completion(rec)



    def _handle_response_audio_done(self, _msg: models.ResponseAudioDoneMessage) -> None:
        self.state.apply_response_audio_done(_msg)
        logger.debug("_handle_response_audio_done: received audio done message")



    def _handle_turn_completion(self, rec: TurnRecord) -> None:
        print('attempting turn complete')
        logger.debug("_handle_turn_completion: evaluating turn completion")
        # If inputs are not complete yet, debounce a check in 200ms
        if not rec.inputs_complete:
            # Cancel any existing timer
            t = self._debounce_timers.pop(cast(models.ResponseID, rec.response_id), None)
            if t:
                t.cancel()
            def _cb() -> None:
                # Recompute and if complete, export
                if self._inputs_complete_for_turn(rec):
                    rec.inputs_complete = True
                    self._on_client_complete(rec)
                if rec.inputs_complete and rec.response_done:
                    self._on_response_complete(rec)
            timer = threading.Timer(0.1, _cb)
            self._debounce_timers[cast(models.ResponseID, rec.response_id)] = timer
            timer.start()
            return
        # If inputs are complete and response is done, export
        if rec.inputs_complete and rec.response_done:
            self._on_response_complete(rec)

    def _on_response_complete(self, rec: TurnRecord) -> None:
        if not rec.response_id:
            logger.warning("_on_response_complete: missing response_id; cannot finish call")
            return
        resp = self.state.get_response(rec.response_id)
        if not resp:
            logger.warning("_on_response_complete: response missing")
            return

        # Skip exports for non-message-only responses (e.g., pure function_call turns)
        has_assistant_message = any(isinstance(it, models.ResponseMessageItem) and it.role == "assistant" for it in resp.output)
        if not has_assistant_message:
            logger.debug("_on_response_complete: no assistant message in output; skipping export for response_id=%s", rec.response_id)
            return

        # Export turn payload if configured
        # Finish the weave call for this response. If the call does not exist yet
        # but inputs are already complete, create it here and immediately finish.
        sess = self.state.session
        if not sess:
            logger.warning("_on_response_complete: no session; cannot create/finish call for response_id=%s", rec.response_id)
            return
        call = self._weave_calls.get(rec.response_id)
        try:
            import weave
            with weave.thread(sess.id):
                from weave.trace.context.weave_client_context import get_weave_client
                client = get_weave_client()
                if not client:
                    logger.warning("_on_response_complete: no weave client in context; skipping finish for response_id=%s", rec.response_id)
                    return
                # Create call on-demand if missing but inputs are complete
                if call is None and rec.inputs_complete:
                    inputs = self._build_inputs_payload(rec)
                    try:
                        from sessions import conversation_turn  # type: ignore
                    except Exception as e:
                        logger.warning("_on_response_complete: failed to import conversation_turn op: %s", e)
                        return
                    call = client.create_call(op=conversation_turn, inputs=inputs)
                    self._weave_calls[rec.response_id] = call
                if call is None:
                    logger.warning("_on_response_complete: call still None; cannot finish for response_id=%s", rec.response_id)
                    return
                outputs = self._build_output_payload(rec)
                client.finish_call(call, output=outputs)
        except Exception as e:
            logger.error(f"Error submitting call in _on_response_complete - {e}")
            return

    def _handle_error(self, msg: models.ErrorMessage) -> None:
        # Let the client handle api errors
        pass

    def _handle_rate_limits_updated(self, msg: models.RateLimitsUpdatedMessage) -> None:
        # Log rate limits for informational purposes
        logger.debug("Rate limits updated: %s", msg.rate_limits)
