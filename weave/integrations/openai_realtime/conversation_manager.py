from __future__ import annotations

import asyncio
import base64
from threading import Lock
from typing import Optional, Union, cast
import threading
import time
import logging

from pydantic import BaseModel, Field

from weave.integrations.openai_realtime import models
from weave.integrations.openai_realtime.encoding import pcm_to_wav
from weave.type_wrappers.Content import Content
from weave.integrations.openai_realtime.handler_registry import EventHandlerGroups, EventHandlerRegistry
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

        self._register_handlers()

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
            logger.error("process_event: event missing 'type': %r", event)
            return
        handler = self._registry.get(event_type)
        if handler:
            with self._lock:
                handler(event)
                # After every event, opportunistically check any pending input completions
                self._maybe_check_all_turns()
        else:
            logger.warning("process_event: no handler registered for event type '%s'", event_type)

    def get_conversation_history(self) -> list[StoredItem]:
        return [self.state.items[iid] for iid in self.state.timeline if iid in self.state.items]

    def get_item(self, item_id: models.ItemID) -> Optional[StoredItem]:
        return self.state.items.get(item_id)


    def get_audio_segment(self, item_id: models.ItemID) -> Optional[bytes]:
        markers = self.state.speech_markers.get(item_id)
        if not markers:
            return None
        start_ms = markers.get("audio_start_ms")
        end_ms = markers.get("audio_end_ms")
        if start_ms is None or end_ms is None:
            return None
        return self.state.input_audio_buffer.get_segment_ms(start_ms, end_ms)

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
            for rid, r in self.state.responses.items():
                for oit in getattr(r, "output", []) or []:
                    if getattr(oit, "id", None) == iid:
                        return rid
            return None

        # Helper: base64 encode a single user audio segment (if we have markers)
        def _encode_user_audio(iid: models.ItemID) -> Optional[Content]:
            seg = self.get_audio_segment(iid)
            if not seg:
                return None
            try:
                return Content.from_bytes(pcm_to_wav(seg), extension=".wav")
            except Exception as e:
                logger.warning("_build_inputs_payload: failed to base64-encode user audio for item_id=%s: %s", iid, e)
                return None

        messages: list[dict[str, object]] = []

        for iid in item_ids:
            it = self.state.items.get(iid)
            if it is None:
                continue

            if isinstance(it, models.ServerSystemMessageItem):
                texts: list[str] = []
                for p in (it.content or []):
                    if getattr(p, "type", None) in ("input_text", "text"):
                        txt = getattr(p, "text", None)
                        if txt:
                            texts.append(txt)
                messages.append({
                    "role": "system",
                    "content": "\n".join(texts) if texts else "",
                })
                continue

            if isinstance(it, models.ServerUserMessageItem):
                transcript: Optional[str] = None
                for p in (it.content or []):
                    if getattr(p, "type", None) == "input_audio":
                        t = getattr(p, "transcript", None)
                        if t:
                            transcript = t
                            break
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "audio",
                            "audio": {
                                "transcript": transcript or "",
                                "data": _encode_user_audio(iid),
                                "format": (sess.input_audio_format if sess else "pcm16"),
                            },
                        }
                    ],
                })
                continue

            if isinstance(it, models.ServerAssistantMessageItem):
                rid = _response_id_for_item(iid)
                parts: list[dict[str, object]] = []
                for idx, p in enumerate(it.content or []):
                    if getattr(p, "type", None) == "audio":
                        b64 = None
                        if rid is not None:
                            buf = self.state.resp_audio_bytes.get((rid, iid, idx))
                            if buf:
                                try:
                                    b64 = base64.b64encode(bytes(buf)).decode("ascii")
                                except Exception as e:
                                    logger.warning("_build_inputs_payload: failed to base64-encode assistant audio (rid=%s,iid=%s,idx=%s): %s", rid, iid, idx, e)
                                    b64 = None
                        parts.append({
                            "type": "audio",
                            "audio": {
                                "transcript": getattr(p, "transcript", None) or "",
                                "data": b64,
                                "format": (sess.output_audio_format if sess else "pcm16"),
                            },
                        })
                messages.append({
                    "role": "assistant",
                    "content": parts or None,
                    "refusal": None,
                    "annotations": [],
                    "function_call": None,
                    "tool_calls": None,
                })
                continue

            if getattr(it, "type", None) == "function_call":
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "refusal": None,
                    "annotations": [],
                    "function_call": None,
                    "tool_calls": [
                        {
                            "id": getattr(it, "call_id", None),
                            "type": "function",
                            "function": {
                                "name": getattr(it, "name", None),
                                "arguments": getattr(it, "arguments", None),
                            },
                        }
                    ],
                })
                continue

            if getattr(it, "type", None) == "function_call_output":
                call_id = getattr(it, "call_id", None)
                name = None
                for other in self.state.items.values():
                    if getattr(other, "type", None) == "function_call" and getattr(other, "call_id", None) == call_id:
                        name = getattr(other, "name", None)
                        break
                messages.append({
                    "role": "tool",
                    "content": getattr(it, "output", None),
                    "tool_call_id": call_id,
                    "name": name,
                })
                continue

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

        # Build assistant message content
        content: list[dict[str, object]] = []
        for it in resp.output:
            if isinstance(it, models.ResponseMessageItem) and getattr(it, "role", None) == "assistant":
                for idx, p in enumerate(it.content or []):
                    if getattr(p, "type", None) == "audio":
                        b64: Optional[str] = None
                        buf = self.state.resp_audio_bytes.get((resp.id, it.id, idx))
                        if buf:
                            try:
                                b64 = base64.b64encode(bytes(buf)).decode("ascii")
                            except Exception as e:
                                logger.warning("_build_output_payload: failed to base64-encode assistant audio (rid=%s,iid=%s,idx=%s): %s", resp.id, it.id, idx, e)
                                b64 = None
                        content.append({
                            "type": "audio",
                            "audio": {
                                "transcript": getattr(p, "transcript", None) or "",
                                "data": b64,
                                "format": (sess.output_audio_format if sess else "pcm16"),
                            },
                        })

        assistant_message: dict[str, object] = {
            "role": "assistant",
            "content": content or None,
            "refusal": None,
            "annotations": [],
            "function_call": None,
            "tool_calls": None,
        }

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

    def _register_handlers(self) -> None:
        groups = EventHandlerGroups()

        # Session
        groups.register_session("session.created", self._handle_session_created)
        groups.register_session("session.updated", self._handle_session_updated)
        groups.register_session("session.update", self._handle_session_update)

        # Input audio buffer lifecycle
        groups.register_input_audio("input_audio_buffer.append", self._handle_input_audio_append)
        groups.register_input_audio("input_audio_buffer.cleared", self._handle_input_audio_cleared)
        groups.register_input_audio("input_audio_buffer.committed", self._handle_input_audio_committed)
        groups.register_input_audio("input_audio_buffer.speech_started", self._handle_speech_started)
        groups.register_input_audio("input_audio_buffer.speech_stopped", self._handle_speech_stopped)

        # Conversation item changes
        groups.register_item("conversation.item.create", self._handle_item_create)
        groups.register_item("conversation.item.created", self._handle_item_created)
        groups.register_item("conversation.item.truncated", self._handle_item_truncated)
        groups.register_item("conversation.item.deleted", self._handle_item_deleted)
        groups.register_item(
            "conversation.item.input_audio_transcription.delta",
            self._handle_item_input_audio_transcription_delta,
        )
        groups.register_item(
            "conversation.item.input_audio_transcription.completed",
            self._handle_item_input_audio_transcription_completed,
        )

        # Response lifecycle and parts
        groups.register_response("response.create", self._handle_response_create)
        groups.register_response("response.created", self._handle_response_created)
        groups.register_response("response.cancel", self._handle_response_cancel)
        groups.register_response("response.done", self._handle_response_done)
        groups.register_response("response.output_item.added", self._handle_response_output_item_added)
        groups.register_response("response.output_item.done", self._handle_response_output_item_done)
        groups.register_response("response.content_part.added", self._handle_response_content_part_added)
        groups.register_response("response.content_part.done", self._handle_response_content_part_done)
        groups.register_response("response.text.delta", self._handle_response_text_delta)
        groups.register_response("response.text.done", self._handle_response_text_done)
        groups.register_response("response.audio_transcript.delta", self._handle_response_audio_transcript_delta)
        groups.register_response("response.audio_transcript.done", self._handle_response_audio_transcript_done)
        groups.register_response("response.audio.delta", self._handle_response_audio_delta)
        groups.register_response("response.audio.done", self._handle_response_audio_done)
        groups.register_response(
            "response.function_call_arguments.delta", self._handle_response_function_call_arguments_delta
        )
        groups.register_response(
            "response.function_call_arguments.done", self._handle_response_function_call_arguments_done
        )

        # Error handling
        groups.register_error("error", self._handle_error)

        # Rate limits
        groups.register_rate_limits("rate_limits.updated", self._handle_rate_limits_updated)

        self._registry.bulk_register(groups.to_dispatch_table())

    # Session
    def _handle_session_created(self, msg: models.SessionCreatedMessage) -> None:
        self.state.session = msg.session

    def _handle_session_updated(self, msg: models.SessionUpdatedMessage) -> None:
        self.state.session = msg.session

    def _handle_session_update(self, msg: models.SessionUpdateMessage) -> None:
        # Client-side session update request - no state changes needed
        logger.debug("Session update request received: %s", msg.type)

    # Input audio buffer
    def _handle_input_audio_append(self, msg: models.InputAudioBufferAppendMessage) -> None:
        self.state.input_audio_buffer.append_base64(msg.audio)

    def _handle_input_audio_cleared(self, _msg: models.InputAudioBufferClearedMessage) -> None:
        self.state.input_audio_buffer.clear()

    def _handle_input_audio_committed(self, msg: models.InputAudioBufferCommittedMessage) -> None:
        # Track commits against items for turn completeness checks
        self.state.committed_item_ids.add(msg.item_id)

    def _handle_speech_started(self, msg: models.InputAudioBufferSpeechStartedMessage) -> None:
        self.state.speech_markers[msg.item_id] = {
            "audio_start_ms": msg.audio_start_ms,
            "audio_end_ms": None,
        }

    def _handle_speech_stopped(self, msg: models.InputAudioBufferSpeechStoppedMessage) -> None:
        markers = self.state.speech_markers.setdefault(msg.item_id, {"audio_start_ms": None, "audio_end_ms": None})
        markers["audio_end_ms"] = msg.audio_end_ms

    # Conversation items
    def _handle_item_create(self, msg: models.ItemCreateMessage) -> None:
        # Client-side item create request - no state changes needed yet
        logger.debug("Item create request received: %s", msg.type)

    def _handle_item_created(self, msg: models.ItemCreatedMessage) -> None:
        item = msg.item
        self.state.items[item.id] = item
        self.state.timeline.append(item.id)

    def _handle_item_truncated(self, msg: models.ItemTruncatedMessage) -> None:
        # If audio was truncated, adjust end marker for that item if present
        markers = self.state.speech_markers.get(msg.item_id)
        if markers and markers.get("audio_end_ms"):
            # Convert audio_end_ms (ms) to samples and then to ms boundary using session rate if desired
            # For now, trust provided ms and leave as-is, as we slice by ms.
            logger.debug("_handle_item_truncated: audio_end_ms already set for item_id=%s; leaving markers as-is", msg.item_id)

    def _handle_item_deleted(self, msg: models.ItemDeletedMessage) -> None:
        self.state.items.pop(msg.item_id, None)
        try:
            self.state.timeline.remove(msg.item_id)
        except ValueError:
            logger.debug("_handle_item_deleted: item_id=%s not present in timeline", msg.item_id)

    def _handle_item_input_audio_transcription_delta(self, msg: models.ItemInputAudioTranscriptionDeltaMessage) -> None:
        key = (msg.item_id, msg.content_index)
        curr = self.state.input_transcripts.get(key, "")
        self.state.input_transcripts[key] = curr + msg.delta

        # Also mirror into the stored item content if present
        item = self.state.items.get(msg.item_id)
        if isinstance(item, (models.ServerUserMessageItem, models.ServerAssistantMessageItem, models.ServerSystemMessageItem)):
            try:
                part = item.content[msg.content_index]
                if isinstance(part, models.InputAudioContentPart):
                    part.transcript = (part.transcript or "") + msg.delta
            except Exception as e:
                logger.error(f"Error _handle_item_input_audio_transcription_delta - {e}")
                # continue without raising
                pass

    def _handle_item_input_audio_transcription_completed(self, msg: models.ItemInputAudioTranscriptionCompletedMessage) -> None:
        key = (msg.item_id, msg.content_index)
        self.state.input_transcripts[key] = msg.transcript

        item = self.state.items.get(msg.item_id)
        if isinstance(item, (models.ServerUserMessageItem, models.ServerAssistantMessageItem, models.ServerSystemMessageItem)):
            try:
                part = item.content[msg.content_index]
                if isinstance(part, models.InputAudioContentPart):
                    part.transcript = msg.transcript
            except Exception as e:
                logger.error("_handle_item_input_audio_transcription_completed: failed to set transcript for item_id=%s index=%s: %s", msg.item_id, msg.content_index, e)
                # continue without raising
                pass

    # Responses
    def _handle_response_create(self, msg: models.ResponseCreateMessage) -> None:
        # Stash any provided custom input items to use as user-side context for the upcoming response
        ctx: Optional[CustomInputContext] = None
        if msg.response and (msg.response.input_items or msg.response.append_input_items):
            ctx = CustomInputContext(input_items=msg.response.input_items, append_input_items=msg.response.append_input_items)
        self.state.pending_custom_context = ctx
        # Record a pending turn awaiting server response.created
        tr = TurnRecord(saw_response_create=True)
        self._pending_create_queue.append(tr)

    def _handle_response_created(self, msg: models.ResponseCreatedMessage) -> None:
        resp = msg.response
        self.state.responses[resp.id] = resp

        # Associate context
        if self.state.pending_custom_context is not None:
            user_ctx: Union[TimelineContext, CustomInputContext]
            user_ctx = self.state.pending_custom_context.model_copy()
        else:
            # In-band: use full conversation so far for the user-side turn
            user_ctx = cast(TimelineContext, {"timeline_items": list(self.state.timeline)})

        self.state.response_context[resp.id] = {
            "user_context": user_ctx,
            "assistant_context": {
                "timeline_items": list(self.state.timeline),
            },
        }

        # Clear pending context once associated
        self.state.pending_custom_context = None
        # Bind to a TurnRecord
        rec = self._get_or_create_turn_for_created(resp.id)
        # If a pending create existed earlier, preserve that flag
        if not rec.saw_response_create and self._pending_create_queue:
            # Already handled above, so nothing here
            pass

    def _handle_response_cancel(self, msg: models.ResponseCancelMessage) -> None:
        # Client-side response cancel request
        logger.debug("Response cancel request received: %s", msg.type)

    def _handle_response_done(self, msg: models.ResponseDoneMessage) -> None:
        self.state.responses[msg.response.id] = msg.response
        # Mark output complete for this turn and handle export logic
        rec = self._ensure_turn_for_resp(msg.response.id)
        if not rec:
            logger.warning("_handle_response_done: missing TurnRecord for response_id=%s", msg.response.id)
            return
        rec.response_done = True
        self._handle_turn_completion(rec)

    def _handle_response_output_item_added(self, msg: models.ResponseOutputItemAddedMessage) -> None:
        # Ensure response exists
        resp = self.state.responses.setdefault(
            msg.response_id,
            models.Response(id=msg.response_id, status="in_progress", status_details=None, output=[], usage=None, conversation_id=None),
        )
        # Append/merge the item
        # If it's already present in output list at index, replace; else append
        if msg.output_index < len(resp.output):
            resp.output[msg.output_index] = msg.item
        else:
            resp.output.append(msg.item)

        # Also put into items store for global access (will be updated by conversation.item.created too)
        self.state.items[msg.item.id] = msg.item

        # If no custom context was set on create, capture timeline so far for this response as context
        self.state.response_context.setdefault(msg.response_id, {
            "user_context": {"timeline_items": list(self.state.timeline)},
            "assistant_context": {"timeline_items": list(self.state.timeline)},
        })

    def _handle_response_output_item_done(self, msg: models.ResponseOutputItemDoneMessage) -> None:
        # Replace final item in response output
        resp = self.state.responses.get(msg.response_id)
        if resp is not None:
            if msg.output_index < len(resp.output):
                resp.output[msg.output_index] = msg.item

        # Update items store as well
        self.state.items[msg.item.id] = msg.item

    def _handle_response_content_part_added(self, msg: models.ResponseContentPartAddedMessage) -> None:
        resp = self.state.responses.get(msg.response_id)
        if not resp:
            logger.warning("_handle_response_content_part_added: response not found for response_id=%s", msg.response_id)
            return
        # Ensure item exists in response output
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
        except StopIteration:
            logger.warning("_handle_response_content_part_added: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return
        # Ensure content list has a slot for the index
        if isinstance(item, models.ResponseMessageItem):
            while len(item.content) <= msg.content_index:
                # Placeholder text part to be filled by deltas; type is resolved on first delta/done
                item.content.append(msg.part)
        else:
            # Function call items don't have content parts list
            pass

        # Initialize delta accumulators
        key = (msg.response_id, msg.item_id, msg.content_index)
        if msg.part.type == "text":
            self.state.resp_text_parts.setdefault(key, "")
        elif msg.part.type == "audio":
            self.state.resp_audio_transcripts.setdefault(key, "")
            self.state.resp_audio_bytes.setdefault(key, bytearray())

    def _handle_response_content_part_done(self, msg: models.ResponseContentPartDoneMessage) -> None:
        # On done, write final values back into the response item content
        resp = self.state.responses.get(msg.response_id)
        if not resp:
            logger.warning("_handle_response_content_part_done: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
        except StopIteration:
            logger.warning("_handle_response_content_part_done: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return
        if isinstance(item, models.ResponseMessageItem):
            # Ensure content list index exists
            while len(item.content) <= msg.content_index:
                item.content.append(msg.part)
            item.content[msg.content_index] = msg.part

    def _handle_response_text_delta(self, msg: models.ResponseTextDeltaMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        curr = self.state.resp_text_parts.get(key, "")
        self.state.resp_text_parts[key] = curr + msg.delta

        # Mirror into the response item content if present
        resp = self.state.responses.get(msg.response_id)
        if not resp:
            logger.warning("_handle_response_text_delta: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, models.ResponseMessageItem):
                # Ensure a text part exists at index
                while len(item.content) <= msg.content_index:
                    item.content.append(models.ResponseItemTextContentPart(type="text", text=""))
                part = item.content[msg.content_index]
                if isinstance(part, models.ResponseItemTextContentPart):
                    part.text = (part.text or "") + msg.delta
        except StopIteration:
            logger.warning("_handle_response_text_delta: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return

    def _handle_response_text_done(self, msg: models.ResponseTextDoneMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        self.state.resp_text_parts[key] = msg.text

        resp = self.state.responses.get(msg.response_id)
        if not resp:
            logger.warning("_handle_response_text_done: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, models.ResponseMessageItem):
                while len(item.content) <= msg.content_index:
                    item.content.append(models.ResponseItemTextContentPart(type="text", text=""))
                item.content[msg.content_index] = models.ResponseItemTextContentPart(type="text", text=msg.text)
        except StopIteration:
            logger.warning("_handle_response_text_done: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return

    def _handle_response_audio_transcript_delta(self, msg: models.ResponseAudioTranscriptDeltaMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        curr = self.state.resp_audio_transcripts.get(key, "")
        self.state.resp_audio_transcripts[key] = curr + msg.delta

        # Mirror into ResponseMessageItem audio part transcript if present
        resp = self.state.responses.get(msg.response_id)
        if not resp:
            logger.warning("_handle_response_audio_transcript_delta: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, models.ResponseMessageItem):
                while len(item.content) <= msg.content_index:
                    item.content.append(models.ResponseItemAudioContentPart(type="audio", transcript=""))
                part = item.content[msg.content_index]
                if isinstance(part, models.ResponseItemAudioContentPart):
                    part.transcript = (part.transcript or "") + msg.delta
        except StopIteration:
            logger.warning("_handle_response_audio_transcript_delta: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return

    def _handle_response_audio_transcript_done(self, msg: models.ResponseAudioTranscriptDoneMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        self.state.resp_audio_transcripts[key] = msg.transcript

        resp = self.state.responses.get(msg.response_id)
        if not resp:
            logger.warning("_handle_response_audio_transcript_done: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, models.ResponseMessageItem):
                while len(item.content) <= msg.content_index:
                    item.content.append(models.ResponseItemAudioContentPart(type="audio", transcript=""))
                item.content[msg.content_index] = models.ResponseItemAudioContentPart(
                    type="audio", transcript=msg.transcript
                )
        except StopIteration:
            logger.warning("_handle_response_audio_transcript_done: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return

    def _handle_response_audio_delta(self, msg: models.ResponseAudioDeltaMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        buf = self.state.resp_audio_bytes.setdefault(key, bytearray())
        try:
            buf.extend(base64.b64decode(msg.delta))
        except Exception as e:
            # Ignore placeholder strings in fixtures, but log for visibility
            logger.warning("_handle_response_audio_delta: failed to base64-decode audio (rid=%s,iid=%s,idx=%s): %s", msg.response_id, msg.item_id, msg.content_index, e)
            pass

    def _handle_response_audio_done(self, _msg: models.ResponseAudioDoneMessage) -> None:
        # No-op for now; bytes are accumulated in resp_audio_bytes
        logger.debug("_handle_response_audio_done: received audio done message")

    def _handle_response_function_call_arguments_delta(
        self, msg: models.ResponseFunctionCallArgumentsDeltaMessage
    ) -> None:
        key = (msg.response_id, msg.call_id)
        curr = self.state.resp_func_args.get(key, "")
        self.state.resp_func_args[key] = curr + msg.delta

    def _handle_response_function_call_arguments_done(
        self, msg: models.ResponseFunctionCallArgumentsDoneMessage
    ) -> None:
        key = (msg.response_id, msg.call_id)
        self.state.resp_func_args[key] = msg.arguments

    def _handle_turn_completion(self, rec: TurnRecord) -> None:
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
        # Only export turns for completed responses (skip cancelled/incomplete)
        if not rec.response_id:
            logger.warning("_on_response_complete: missing response_id; cannot finish call")
            return
        resp = self.state.get_response(rec.response_id)
        if not resp:
            logger.warning("_on_response_complete: response missing")
            return
        # Skip exports for non-message-only responses (e.g., pure function_call turns)
        has_assistant_message = any(
            isinstance(it, models.ResponseMessageItem) and getattr(it, "role", None) == "assistant"
            for it in getattr(resp, "output", [])
        )
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
        # Log error messages
        logger.error("API Error: type=%s, message=%s, code=%s", 
                     msg.error.type, msg.error.message, msg.error.code)

    def _handle_rate_limits_updated(self, msg: models.RateLimitsUpdatedMessage) -> None:
        # Log rate limits for informational purposes
        logger.debug("Rate limits updated: %s", msg.rate_limits)
