from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable, Dict, List, Optional, Tuple, Union, TypeVar, cast, TypedDict, overload, Literal
import threading
import time
import os
import json

from pydantic import BaseModel, Field

from models import (
    ClientItem,
    InputAudioBufferAppendMessage,
    InputAudioBufferClearedMessage,
    InputAudioBufferCommittedMessage,
    InputAudioBufferSpeechStartedMessage,
    InputAudioBufferSpeechStoppedMessage,
    ItemCreatedMessage,
    ItemDeletedMessage,
    ItemID,
    ItemInputAudioTranscriptionCompletedMessage,
    ItemInputAudioTranscriptionDeltaMessage,
    ItemTruncatedMessage,
    MessageType,
    Response,
    ResponseAudioDeltaMessage,
    ResponseAudioDoneMessage,
    ResponseAudioTranscriptDeltaMessage,
    ResponseAudioTranscriptDoneMessage,
    ResponseContentPartAddedMessage,
    ResponseContentPartDoneMessage,
    ResponseCreateMessage,
    ResponseCreatedMessage,
    ResponseDoneMessage,
    ResponseFunctionCallArgumentsDeltaMessage,
    ResponseFunctionCallArgumentsDoneMessage,
    ResponseID,
    ResponseItem,
    ResponseMessageItem,
    ResponseItemTextContentPart,
    ResponseItemAudioContentPart,
    ResponseOutputItemAddedMessage,
    ResponseOutputItemDoneMessage,
    ResponseTextDeltaMessage,
    ResponseTextDoneMessage,
    Session,
    SessionCreatedMessage,
    SessionUpdatedMessage,
    ServerItem,
    ServerUserMessageItem,
    ServerAssistantMessageItem,
    ServerSystemMessageItem,
    InputAudioContentPart,
    ResponseMessageItem,
)


@dataclass
class AudioBufferManager:
    """
    Maintains a single, continuous PCM audio buffer for a conversation and
    provides helpers to slice out segments by millisecond offsets.

    Default format: 16-bit PCM, mono, 24kHz (extensible).
    """

    sample_rate_hz: int = 24000
    bits_per_sample: int = 16
    channels: int = 1
    buffer: bytearray = field(default_factory=bytearray)

    def bytes_per_sample(self) -> int:
        return (self.bits_per_sample // 8) * self.channels

    def append_base64(self, b64: str) -> None:
        """Decode base64 audio and append. Ignores invalid payloads gracefully."""
        try:
            self.buffer.extend(base64.b64decode(b64))
        except Exception:
            # Some fixtures use placeholder strings like "<audio bytes>".
            # Skip invalid base64 without failing the pipeline.
            pass

    def clear(self) -> None:
        self.buffer.clear()

    def _ms_to_byte_range(self, start_ms: int, end_ms: int) -> Tuple[int, int]:
        bps = self.bytes_per_sample()
        start_samples = int((start_ms / 1000.0) * self.sample_rate_hz)
        end_samples = int((end_ms / 1000.0) * self.sample_rate_hz)
        return start_samples * bps, end_samples * bps

    def get_segment_ms(self, start_ms: int, end_ms: int) -> bytes:
        start_b, end_b = self._ms_to_byte_range(start_ms, end_ms)
        start_b = max(0, start_b)
        end_b = min(len(self.buffer), max(start_b, end_b))
        return bytes(self.buffer[start_b:end_b])


StoredItem = Union[ServerItem, ResponseItem]


class TimelineContext(TypedDict):
    timeline_items: List[ItemID]


class CustomInputContext(TypedDict, total=False):
    input_items: List[ClientItem]
    append_input_items: List[ClientItem]


class ResponseContext(TypedDict):
    user_context: Union[TimelineContext, CustomInputContext]
    assistant_context: TimelineContext


class StateStore(BaseModel):
    """
    Central state for a single conversation session.
    Tracks session, items, responses, audio buffer, speech markers, and delta accumulators.
    """

    model_config = {"arbitrary_types_allowed": True}

    session: Optional[Session] = None
    items: Dict[ItemID, StoredItem] = Field(default_factory=dict)
    responses: Dict[ResponseID, Response] = Field(default_factory=dict)

    # Maintains timeline order of created items (IDs) to help derive context.
    timeline: List[ItemID] = Field(default_factory=list)

    # Input audio buffer and speech markers per item
    input_audio_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)
    speech_markers: Dict[ItemID, Dict[str, Optional[int]]] = Field(default_factory=dict)

    # Delta accumulation helpers
    # - For user item input_audio transcription (by item_id -> text)
    input_transcripts: Dict[Tuple[ItemID, int], str] = Field(default_factory=dict)

    # - For response text parts (response_id, item_id, content_index) -> text
    resp_text_parts: Dict[Tuple[ResponseID, ItemID, int], str] = Field(default_factory=dict)

    # - For response audio transcript parts (response_id, item_id, content_index) -> transcript text
    resp_audio_transcripts: Dict[Tuple[ResponseID, ItemID, int], str] = Field(default_factory=dict)

    # - For response audio raw bytes accumulation (response_id, item_id, content_index) -> bytes
    resp_audio_bytes: Dict[Tuple[ResponseID, ItemID, int], bytearray] = Field(default_factory=dict)

    # - For function call arguments accumulation (response_id, call_id) -> args string
    resp_func_args: Dict[Tuple[ResponseID, str], str] = Field(default_factory=dict)

    # Response context mapping
    # Stores two views: user_context (what model used on user side) and assistant_context (full context)
    response_context: Dict[ResponseID, ResponseContext] = Field(default_factory=dict)

    # Pending custom context registered on ResponseCreateMessage until a ResponseCreatedMessage materializes
    pending_custom_context: Optional[CustomInputContext] = None

    # Input tracking helpers
    committed_item_ids: set[ItemID] = Field(default_factory=set)


class TurnRecord(BaseModel):
    """Tracks a single turn keyed by response_id."""

    response_id: Optional[ResponseID] = None
    created_at: float = Field(default_factory=lambda: time.time())
    user_context: Optional[Union[TimelineContext, CustomInputContext]] = None
    assistant_context: Optional[TimelineContext] = None
    inputs_complete: bool = False
    response_done: bool = False
    index: int = 0
    # Internal: we saw a user 'response.create' for this turn before server 'response.created'
    saw_response_create: bool = False


Handler = Callable[[MessageType], None]


class EventHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, Handler] = {}

    T_msg = TypeVar("T_msg", bound=MessageType)

    def register(self, event_type: str, handler: Callable[[T_msg], None]) -> None:
        # Safe cast: the registry only dispatches the matching event type
        self._handlers[event_type] = cast(Handler, handler)

    def get(self, event_type: str) -> Optional[Handler]:
        return self._handlers.get(event_type)

    def bulk_register(self, mapping: Dict[str, Handler]) -> None:
        self._handlers.update(mapping)



SessionEventType = Union[Literal["session.created"], Literal["session.updated"]]
InputAudioEventType = Union[
    Literal["input_audio_buffer.append"],
    Literal["input_audio_buffer.cleared"],
    Literal["input_audio_buffer.committed"],
    Literal["input_audio_buffer.speech_started"],
    Literal["input_audio_buffer.speech_stopped"],
]
ItemEventType = Union[
    Literal["conversation.item.created"],
    Literal["conversation.item.truncated"],
    Literal["conversation.item.deleted"],
    Literal["conversation.item.input_audio_transcription.delta"],
    Literal["conversation.item.input_audio_transcription.completed"],
]
ResponseEventType = Union[
    Literal["response.create"],
    Literal["response.created"],
    Literal["response.done"],
    Literal["response.output_item.added"],
    Literal["response.output_item.done"],
    Literal["response.content_part.added"],
    Literal["response.content_part.done"],
    Literal["response.text.delta"],
    Literal["response.text.done"],
    Literal["response.audio_transcript.delta"],
    Literal["response.audio_transcript.done"],
    Literal["response.audio.delta"],
    Literal["response.audio.done"],
    Literal["response.function_call_arguments.delta"],
    Literal["response.function_call_arguments.done"],
]

SessionMessage = Union[SessionCreatedMessage, SessionUpdatedMessage]
InputAudioBufferMessage = Union[
    InputAudioBufferAppendMessage,
    InputAudioBufferClearedMessage,
    InputAudioBufferCommittedMessage,
    InputAudioBufferSpeechStartedMessage,
    InputAudioBufferSpeechStoppedMessage,
]
ItemMessage = Union[
    ItemCreatedMessage,
    ItemTruncatedMessage,
    ItemDeletedMessage,
    ItemInputAudioTranscriptionDeltaMessage,
    ItemInputAudioTranscriptionCompletedMessage,
]
ResponseEvent = Union[
    ResponseCreateMessage,
    ResponseCreatedMessage,
    ResponseDoneMessage,
    ResponseOutputItemAddedMessage,
    ResponseOutputItemDoneMessage,
    ResponseContentPartAddedMessage,
    ResponseContentPartDoneMessage,
    ResponseTextDeltaMessage,
    ResponseTextDoneMessage,
    ResponseAudioTranscriptDeltaMessage,
    ResponseAudioTranscriptDoneMessage,
    ResponseAudioDeltaMessage,
    ResponseAudioDoneMessage,
    ResponseFunctionCallArgumentsDeltaMessage,
    ResponseFunctionCallArgumentsDoneMessage,
]


class EventHandlerGroups:
    def __init__(self) -> None:
        self._dispatch: Dict[str, Handler] = {}

    def _add(self, event_type: str, handler: Callable[..., None]) -> None:
        def wrapper(msg: MessageType, _h=handler) -> None:
            _h(msg)
        self._dispatch[event_type] = wrapper

    # Session
    @overload
    def register_session(self, event_type: Literal["session.created"], handler: Callable[[SessionCreatedMessage], None]) -> None: ...
    @overload
    def register_session(self, event_type: Literal["session.updated"], handler: Callable[[SessionUpdatedMessage], None]) -> None: ...
    def register_session(self, event_type: SessionEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    # Input audio buffer
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.append"], handler: Callable[[InputAudioBufferAppendMessage], None]) -> None: ...
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.cleared"], handler: Callable[[InputAudioBufferClearedMessage], None]) -> None: ...
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.committed"], handler: Callable[[InputAudioBufferCommittedMessage], None]) -> None: ...
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.speech_started"], handler: Callable[[InputAudioBufferSpeechStartedMessage], None]) -> None: ...
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.speech_stopped"], handler: Callable[[InputAudioBufferSpeechStoppedMessage], None]) -> None: ...
    def register_input_audio(self, event_type: InputAudioEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    # Conversation items
    @overload
    def register_item(self, event_type: Literal["conversation.item.created"], handler: Callable[[ItemCreatedMessage], None]) -> None: ...
    @overload
    def register_item(self, event_type: Literal["conversation.item.truncated"], handler: Callable[[ItemTruncatedMessage], None]) -> None: ...
    @overload
    def register_item(self, event_type: Literal["conversation.item.deleted"], handler: Callable[[ItemDeletedMessage], None]) -> None: ...
    @overload
    def register_item(self, event_type: Literal["conversation.item.input_audio_transcription.delta"], handler: Callable[[ItemInputAudioTranscriptionDeltaMessage], None]) -> None: ...
    @overload
    def register_item(self, event_type: Literal["conversation.item.input_audio_transcription.completed"], handler: Callable[[ItemInputAudioTranscriptionCompletedMessage], None]) -> None: ...
    def register_item(self, event_type: ItemEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    # Responses
    @overload
    def register_response(self, event_type: Literal["response.create"], handler: Callable[[ResponseCreateMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.created"], handler: Callable[[ResponseCreatedMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.done"], handler: Callable[[ResponseDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.output_item.added"], handler: Callable[[ResponseOutputItemAddedMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.output_item.done"], handler: Callable[[ResponseOutputItemDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.content_part.added"], handler: Callable[[ResponseContentPartAddedMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.content_part.done"], handler: Callable[[ResponseContentPartDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.text.delta"], handler: Callable[[ResponseTextDeltaMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.text.done"], handler: Callable[[ResponseTextDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.audio_transcript.delta"], handler: Callable[[ResponseAudioTranscriptDeltaMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.audio_transcript.done"], handler: Callable[[ResponseAudioTranscriptDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.audio.delta"], handler: Callable[[ResponseAudioDeltaMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.audio.done"], handler: Callable[[ResponseAudioDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.function_call_arguments.delta"], handler: Callable[[ResponseFunctionCallArgumentsDeltaMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.function_call_arguments.done"], handler: Callable[[ResponseFunctionCallArgumentsDoneMessage], None]) -> None: ...
    def register_response(self, event_type: ResponseEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    def to_dispatch_table(self) -> Dict[str, Handler]:
        return dict(self._dispatch)


class ConversationManager:
    """
    Orchestrates event-driven state management for a conversation.
    Provides async queue submission and direct processing.
    """

    def __init__(self) -> None:
        self.state = StateStore()
        self._registry = EventHandlerRegistry()
        self._queue: asyncio.Queue[MessageType] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = Lock()

        self._register_handlers()

        # Turn tracking
        self._turn_counter = 0
        self._pending_create_queue: List[TurnRecord] = []
        self._turns_by_response: Dict[ResponseID, TurnRecord] = {}
        self._debounce_timers: Dict[ResponseID, threading.Timer] = {}
        self.turn_export_dir: Optional[str] = None  # if set, export completed turns here
        # Export numbering (contiguous across exported turns only)
        self._export_counter: int = 0
        # Populated by connection wrappers if available
        self.client_base_url: Optional[str] = None

    async def start(self) -> None:
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

    async def submit_event(self, event: MessageType) -> None:
        await self._queue.put(event)

    def process_event(self, event: MessageType) -> None:
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

    def get_conversation_history(self) -> List[StoredItem]:
        return [self.state.items[iid] for iid in self.state.timeline if iid in self.state.items]

    def get_item(self, item_id: ItemID) -> Optional[StoredItem]:
        return self.state.items.get(item_id)

    def get_response(self, response_id: ResponseID) -> Optional[Response]:
        return self.state.responses.get(response_id)

    def get_audio_segment(self, item_id: ItemID) -> Optional[bytes]:
        markers = self.state.speech_markers.get(item_id)
        if not markers:
            return None
        start_ms = markers.get("audio_start_ms")
        end_ms = markers.get("audio_end_ms")
        if start_ms is None or end_ms is None:
            return None
        return self.state.input_audio_buffer.get_segment_ms(start_ms, end_ms)

    def export_state(self) -> Dict[str, object]:
        # Export a JSON-serializable snapshot of current state
        items = {str(k): v.model_dump() for k, v in self.state.items.items()}
        responses = {str(k): v.model_dump() for k, v in self.state.responses.items()}
        speech_raw: Dict[str, Dict[str, Optional[int]]] = {str(k): v for k, v in self.state.speech_markers.items()}
        speech = cast(Dict[str, object], speech_raw)
        return {
            "session": self.state.session.model_dump() if self.state.session else None,
            "items": items,
            "responses": responses,
            "timeline": list(self.state.timeline),
            "speech_markers": speech,
        }

    def _get_or_create_turn_for_created(self, resp_id: ResponseID) -> TurnRecord:
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

    def _ensure_turn_for_resp(self, resp_id: ResponseID) -> Optional[TurnRecord]:
        rec = self._turns_by_response.get(resp_id)
        if rec is None:
            rec = self._get_or_create_turn_for_created(resp_id)
        return rec

    def _collect_input_item_ids(self, rec: TurnRecord) -> List[ItemID]:
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
            if not isinstance(it, (ServerUserMessageItem,)):
                continue
            # Check each content part
            for part in getattr(it, "content", []) or []:
                if isinstance(part, InputAudioContentPart):
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
        # Hook for client-complete; currently no-op beyond debug
        # Could log or emit signal; we'll defer actual export until response is done
        pass

    def _export_turn(self, rec: TurnRecord) -> None:
        if not self.turn_export_dir:
            return
        os.makedirs(self.turn_export_dir, exist_ok=True)
        # Use contiguous numbering for exported turns
        self._export_counter += 1
        export_idx = self._export_counter
        path = os.path.join(self.turn_export_dir, f"turn_{export_idx}.json")
        payload = {
            "inputs": self._build_inputs_payload(rec),
            "output": self._build_output_payload(rec),
        }
        with open(path, "w") as f:
            json.dump(payload, f)

    def _build_inputs_payload(self, rec: TurnRecord) -> Dict[str, object]:
        """Build Inputs payload matching the requested schema."""
        sess = self.state.session
        item_ids = self._collect_input_item_ids(rec)

        # Helper: response_id for an assistant message item
        def _response_id_for_item(iid: ItemID) -> Optional[ResponseID]:
            for rid, r in self.state.responses.items():
                for oit in getattr(r, "output", []) or []:
                    if getattr(oit, "id", None) == iid:
                        return rid
            return None

        # Helper: base64 encode a single user audio segment (if we have markers)
        def _encode_user_audio(iid: ItemID) -> Optional[str]:
            seg = self.get_audio_segment(iid)
            if not seg:
                return None
            try:
                return base64.b64encode(seg).decode("ascii")
            except Exception:
                return None

        messages: List[Dict[str, object]] = []

        for iid in item_ids:
            it = self.state.items.get(iid)
            if it is None:
                continue

            if isinstance(it, ServerSystemMessageItem):
                texts: List[str] = []
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

            if isinstance(it, ServerUserMessageItem):
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

            if isinstance(it, ServerAssistantMessageItem):
                rid = _response_id_for_item(iid)
                parts: List[Dict[str, object]] = []
                for idx, p in enumerate(it.content or []):
                    if getattr(p, "type", None) == "audio":
                        b64 = None
                        if rid is not None:
                            buf = self.state.resp_audio_bytes.get((rid, iid, idx))
                            if buf:
                                try:
                                    b64 = base64.b64encode(bytes(buf)).decode("ascii")
                                except Exception:
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

    def _build_output_payload(self, rec: TurnRecord) -> Dict[str, object]:
        """Build Output payload matching the requested schema."""
        if not rec.response_id:
            return {}
        resp = self.get_response(rec.response_id)
        if not resp:
            return {}

        sess = self.state.session

        # Build assistant message content
        content: List[Dict[str, object]] = []
        for it in resp.output:
            if isinstance(it, ResponseMessageItem) and getattr(it, "role", None) == "assistant":
                for idx, p in enumerate(it.content or []):
                    if getattr(p, "type", None) == "audio":
                        b64: Optional[str] = None
                        buf = self.state.resp_audio_bytes.get((resp.id, it.id, idx))
                        if buf:
                            try:
                                b64 = base64.b64encode(bytes(buf)).decode("ascii")
                            except Exception:
                                b64 = None
                        content.append({
                            "type": "audio",
                            "audio": {
                                "transcript": getattr(p, "transcript", None) or "",
                                "data": b64,
                                "format": (sess.output_audio_format if sess else "pcm16"),
                            },
                        })

        assistant_message: Dict[str, object] = {
            "role": "assistant",
            "content": content or None,
            "refusal": None,
            "annotations": [],
            "function_call": None,
            "tool_calls": None,
        }

        usage_obj: Optional[Dict[str, object]] = None
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
            "created": None,
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

        # Input audio buffer lifecycle
        groups.register_input_audio("input_audio_buffer.append", self._handle_input_audio_append)
        groups.register_input_audio("input_audio_buffer.cleared", self._handle_input_audio_cleared)
        groups.register_input_audio("input_audio_buffer.committed", self._handle_input_audio_committed)
        groups.register_input_audio("input_audio_buffer.speech_started", self._handle_speech_started)
        groups.register_input_audio("input_audio_buffer.speech_stopped", self._handle_speech_stopped)

        # Conversation item changes
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

        self._registry.bulk_register(groups.to_dispatch_table())

    # Session
    def _handle_session_created(self, msg: SessionCreatedMessage) -> None:
        self.state.session = msg.session

    def _handle_session_updated(self, msg: SessionUpdatedMessage) -> None:
        self.state.session = msg.session

    # Input audio buffer
    def _handle_input_audio_append(self, msg: InputAudioBufferAppendMessage) -> None:
        self.state.input_audio_buffer.append_base64(msg.audio)

    def _handle_input_audio_cleared(self, _msg: InputAudioBufferClearedMessage) -> None:
        self.state.input_audio_buffer.clear()

    def _handle_input_audio_committed(self, msg: InputAudioBufferCommittedMessage) -> None:
        # Track commits against items for turn completeness checks
        self.state.committed_item_ids.add(msg.item_id)

    def _handle_speech_started(self, msg: InputAudioBufferSpeechStartedMessage) -> None:
        self.state.speech_markers[msg.item_id] = {
            "audio_start_ms": msg.audio_start_ms,
            "audio_end_ms": None,
        }

    def _handle_speech_stopped(self, msg: InputAudioBufferSpeechStoppedMessage) -> None:
        markers = self.state.speech_markers.setdefault(msg.item_id, {"audio_start_ms": None, "audio_end_ms": None})
        markers["audio_end_ms"] = msg.audio_end_ms

    # Conversation items
    def _handle_item_created(self, msg: ItemCreatedMessage) -> None:
        item = msg.item
        self.state.items[item.id] = item
        self.state.timeline.append(item.id)

    def _handle_item_truncated(self, msg: ItemTruncatedMessage) -> None:
        # If audio was truncated, adjust end marker for that item if present
        markers = self.state.speech_markers.get(msg.item_id)
        if markers and markers.get("audio_end_ms"):
            # Convert audio_end_ms (ms) to samples and then to ms boundary using session rate if desired
            # For now, trust provided ms and leave as-is, as we slice by ms.
            pass

    def _handle_item_deleted(self, msg: ItemDeletedMessage) -> None:
        self.state.items.pop(msg.item_id, None)
        try:
            self.state.timeline.remove(msg.item_id)
        except ValueError:
            pass

    def _handle_item_input_audio_transcription_delta(self, msg: ItemInputAudioTranscriptionDeltaMessage) -> None:
        key = (msg.item_id, msg.content_index)
        curr = self.state.input_transcripts.get(key, "")
        self.state.input_transcripts[key] = curr + msg.delta

        # Also mirror into the stored item content if present
        item = self.state.items.get(msg.item_id)
        if isinstance(item, (ServerUserMessageItem, ServerAssistantMessageItem, ServerSystemMessageItem)):
            try:
                part = item.content[msg.content_index]
                if isinstance(part, InputAudioContentPart):
                    part.transcript = (part.transcript or "") + msg.delta
            except Exception:
                pass

    def _handle_item_input_audio_transcription_completed(self, msg: ItemInputAudioTranscriptionCompletedMessage) -> None:
        key = (msg.item_id, msg.content_index)
        self.state.input_transcripts[key] = msg.transcript

        item = self.state.items.get(msg.item_id)
        if isinstance(item, (ServerUserMessageItem, ServerAssistantMessageItem, ServerSystemMessageItem)):
            try:
                part = item.content[msg.content_index]
                if isinstance(part, InputAudioContentPart):
                    part.transcript = msg.transcript
            except Exception:
                pass

    # Responses
    def _handle_response_create(self, msg: ResponseCreateMessage) -> None:
        # Stash any provided custom input items to use as user-side context for the upcoming response
        ctx: Optional[CustomInputContext] = None
        if msg.response:
            tmp: CustomInputContext = {}
            if msg.response.input_items is not None:
                tmp["input_items"] = msg.response.input_items
            if msg.response.append_input_items is not None:
                tmp["append_input_items"] = msg.response.append_input_items
            ctx = tmp or None
        self.state.pending_custom_context = ctx
        # Record a pending turn awaiting server response.created
        tr = TurnRecord(saw_response_create=True)
        self._pending_create_queue.append(tr)

    def _handle_response_created(self, msg: ResponseCreatedMessage) -> None:
        resp = msg.response
        self.state.responses[resp.id] = resp

        # Associate context
        if self.state.pending_custom_context is not None:
            user_ctx: Union[TimelineContext, CustomInputContext]
            user_ctx = self.state.pending_custom_context.copy()
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

    def _handle_response_done(self, msg: ResponseDoneMessage) -> None:
        self.state.responses[msg.response.id] = msg.response
        # Mark output complete for this turn and handle export logic
        rec = self._ensure_turn_for_resp(msg.response.id)
        if not rec:
            return
        rec.response_done = True
        self._handle_turn_completion(rec)

    def _handle_response_output_item_added(self, msg: ResponseOutputItemAddedMessage) -> None:
        # Ensure response exists
        resp = self.state.responses.setdefault(
            msg.response_id,
            Response(id=msg.response_id, status="in_progress", status_details=None, output=[], usage=None, conversation_id=None),
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

    def _handle_response_output_item_done(self, msg: ResponseOutputItemDoneMessage) -> None:
        # Replace final item in response output
        resp = self.state.responses.get(msg.response_id)
        if resp is not None:
            if msg.output_index < len(resp.output):
                resp.output[msg.output_index] = msg.item

        # Update items store as well
        self.state.items[msg.item.id] = msg.item

    def _handle_response_content_part_added(self, msg: ResponseContentPartAddedMessage) -> None:
        resp = self.state.responses.get(msg.response_id)
        if not resp:
            return
        # Ensure item exists in response output
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
        except StopIteration:
            return
        # Ensure content list has a slot for the index
        if isinstance(item, ResponseMessageItem):
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

    def _handle_response_content_part_done(self, msg: ResponseContentPartDoneMessage) -> None:
        # On done, write final values back into the response item content
        resp = self.state.responses.get(msg.response_id)
        if not resp:
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
        except StopIteration:
            return
        if isinstance(item, ResponseMessageItem):
            # Ensure content list index exists
            while len(item.content) <= msg.content_index:
                item.content.append(msg.part)
            item.content[msg.content_index] = msg.part

    def _handle_response_text_delta(self, msg: ResponseTextDeltaMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        curr = self.state.resp_text_parts.get(key, "")
        self.state.resp_text_parts[key] = curr + msg.delta

        # Mirror into the response item content if present
        resp = self.state.responses.get(msg.response_id)
        if not resp:
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, ResponseMessageItem):
                # Ensure a text part exists at index
                while len(item.content) <= msg.content_index:
                    item.content.append(ResponseItemTextContentPart(type="text", text=""))
                part = item.content[msg.content_index]
                if isinstance(part, ResponseItemTextContentPart):
                    part.text = (part.text or "") + msg.delta
        except StopIteration:
            return

    def _handle_response_text_done(self, msg: ResponseTextDoneMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        self.state.resp_text_parts[key] = msg.text

        resp = self.state.responses.get(msg.response_id)
        if not resp:
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, ResponseMessageItem):
                while len(item.content) <= msg.content_index:
                    item.content.append(ResponseItemTextContentPart(type="text", text=""))
                item.content[msg.content_index] = ResponseItemTextContentPart(type="text", text=msg.text)
        except StopIteration:
            return

    def _handle_response_audio_transcript_delta(self, msg: ResponseAudioTranscriptDeltaMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        curr = self.state.resp_audio_transcripts.get(key, "")
        self.state.resp_audio_transcripts[key] = curr + msg.delta

        # Mirror into ResponseMessageItem audio part transcript if present
        resp = self.state.responses.get(msg.response_id)
        if not resp:
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, ResponseMessageItem):
                while len(item.content) <= msg.content_index:
                    item.content.append(ResponseItemAudioContentPart(type="audio", transcript=""))
                part = item.content[msg.content_index]
                if isinstance(part, ResponseItemAudioContentPart):
                    part.transcript = (part.transcript or "") + msg.delta
        except StopIteration:
            return

    def _handle_response_audio_transcript_done(self, msg: ResponseAudioTranscriptDoneMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        self.state.resp_audio_transcripts[key] = msg.transcript

        resp = self.state.responses.get(msg.response_id)
        if not resp:
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, ResponseMessageItem):
                while len(item.content) <= msg.content_index:
                    item.content.append(ResponseItemAudioContentPart(type="audio", transcript=""))
                item.content[msg.content_index] = ResponseItemAudioContentPart(
                    type="audio", transcript=msg.transcript
                )
        except StopIteration:
            return

    def _handle_response_audio_delta(self, msg: ResponseAudioDeltaMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        buf = self.state.resp_audio_bytes.setdefault(key, bytearray())
        try:
            buf.extend(base64.b64decode(msg.delta))
        except Exception:
            # Ignore placeholder strings in fixtures
            pass

    def _handle_response_audio_done(self, _msg: ResponseAudioDoneMessage) -> None:
        # No-op for now; bytes are accumulated in resp_audio_bytes
        pass

    def _handle_response_function_call_arguments_delta(
        self, msg: ResponseFunctionCallArgumentsDeltaMessage
    ) -> None:
        key = (msg.response_id, msg.call_id)
        curr = self.state.resp_func_args.get(key, "")
        self.state.resp_func_args[key] = curr + msg.delta

    def _handle_response_function_call_arguments_done(
        self, msg: ResponseFunctionCallArgumentsDoneMessage
    ) -> None:
        key = (msg.response_id, msg.call_id)
        self.state.resp_func_args[key] = msg.arguments

    def _handle_turn_completion(self, rec: TurnRecord) -> None:
        # If inputs are not complete yet, debounce a check in 200ms
        if not rec.inputs_complete:
            # Cancel any existing timer
            t = self._debounce_timers.pop(cast(ResponseID, rec.response_id), None)
            if t:
                t.cancel()
            def _cb() -> None:
                # Recompute and if complete, export
                if self._inputs_complete_for_turn(rec):
                    rec.inputs_complete = True
                    self._on_client_complete(rec)
                if rec.inputs_complete and rec.response_done:
                    self._on_response_complete(rec)
            timer = threading.Timer(0.2, _cb)
            self._debounce_timers[cast(ResponseID, rec.response_id)] = timer
            timer.start()
            return
        # If inputs are complete and response is done, export
        if rec.inputs_complete and rec.response_done:
            self._on_response_complete(rec)

    def _on_response_complete(self, rec: TurnRecord) -> None:
        # Only export turns for completed responses (skip cancelled/incomplete)
        if not rec.response_id:
            return
        resp = self.get_response(rec.response_id)
        if not resp or getattr(resp, "status", None) != "completed":
            return
        # Skip exports for non-message-only responses (e.g., pure function_call turns)
        has_assistant_message = any(
            isinstance(it, ResponseMessageItem) and getattr(it, "role", None) == "assistant"
            for it in getattr(resp, "output", [])
        )
        if not has_assistant_message:
            return
        # Export turn payload if configured
        self._export_turn(rec)
