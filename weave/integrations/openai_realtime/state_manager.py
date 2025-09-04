import logging
import base64
from dataclasses import dataclass, field
from typing import Optional, Union, cast
from typing_extensions import Iterable, TypedDict
from pydantic import BaseModel, Field
from audio_buffer import AudioBufferManager
from weave.integrations.openai_realtime import models

logger = logging.getLogger(__name__)

StoredItem = Union[models.ServerItem, models.ResponseItem]

class TimelineContext(TypedDict):
    timeline_items: list[models.ItemID]


class CustomInputContext(BaseModel):
    input_items: Optional[list[models.ClientItem]]
    append_input_items: Optional[list[models.ClientItem]]


class ResponseContext(TypedDict):
    user_context: Union[TimelineContext, CustomInputContext]
    assistant_context: TimelineContext

class StateStore(BaseModel):
    """
    Central state for a single conversation session.
    Tracks session, items, responses, audio buffer, speech markers, and delta accumulators.
    """
    model_config = {"arbitrary_types_allowed": True}

    session: Optional[models.Session] = None
    items: dict[models.ItemID, StoredItem] = Field(default_factory=dict)
    responses: dict[models.ResponseID, models.Response] = Field(default_factory=dict)

    # Maintains timeline order of created items (IDs) to help derive context.
    # Note: We additionally track a doubly-linked list via prev/next maps to
    # reconstruct a chain around any particular item using previous_item_id.
    timeline: list[models.ItemID] = Field(default_factory=list)
    prev_by_item: dict[models.ItemID, Optional[models.ItemID]] = Field(default_factory=dict)
    next_by_item: dict[models.ItemID, Optional[models.ItemID]] = Field(default_factory=dict)

    call_by_id: dict[models.CallID, models.ResponseFunctionCallItem] = Field(default_factory=dict)
    call_output_by_id: dict[models.CallID, models.ResponseFunctionCallItem] = Field(default_factory=dict)

    # Input audio buffer and speech markers per item
    input_audio_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)
    speech_markers: dict[models.ItemID, dict[str, Optional[int]]] = Field(default_factory=dict)

    # Delta accumulation helpers
    # - For user item input_audio transcription (by item_id -> text)
    input_transcripts: dict[tuple[models.ItemID, int], str] = Field(default_factory=dict)

    # - For response text parts (response_id, item_id, content_index) -> text
    resp_text_parts: dict[tuple[models.ResponseID, models.ItemID, int], str] = Field(default_factory=dict)

    # - For response audio transcript parts (response_id, item_id, content_index) -> transcript text
    resp_audio_transcripts: dict[tuple[models.ResponseID, models.ItemID, int], str] = Field(default_factory=dict)
    # - For response audio raw bytes accumulation (response_id, item_id, content_index) -> bytes
    resp_audio_bytes: dict[tuple[models.ResponseID, models.ItemID, int], bytearray] = Field(default_factory=dict)
    # - For function call arguments accumulation (response_id, call_id) -> args string
    resp_func_args: dict[tuple[models.ResponseID, str], str] = Field(default_factory=dict)

    # Response context mapping
    # Stores two views: user_context (what model used on user side) and assistant_context (full context)
    response_context: dict[models.ResponseID, ResponseContext] = Field(default_factory=dict)

    # Pending custom context registered on ResponseCreateMessage until a ResponseCreatedMessage materializes
    pending_custom_context: Optional[CustomInputContext] = None

    # Input tracking helpers
    committed_item_ids: set[models.ItemID] = Field(default_factory=set)

    def get_item(self, item_id: models.ItemID) -> StoredItem:
        # TODO: Add error handling but i want this to fail for now
        return self.items[item_id]

    def get_conversation_history(self) -> Iterable[StoredItem]:
        for item_id in self.timeline:
            yield self.get_item(item_id)

    def get_response(self, response_id: models.ResponseID) -> Optional[models.Response]:
        return self.responses.get(response_id)

    # ---- Doubly linked list helpers ----
    def link_items(self, prev_item_id: Optional[models.ItemID], curr_item_id: models.ItemID) -> None:
        """
        Record a linkage between two items as part of the conversation chain.
        This uses the provided previous_item_id (if any) to update a doubly-linked
        list structure so we can traverse the chain from any item.
        """
        # Ensure entries exist
        if curr_item_id not in self.prev_by_item:
            self.prev_by_item[curr_item_id] = None
        if curr_item_id not in self.next_by_item:
            self.next_by_item[curr_item_id] = None

        # Link backwards pointer for current
        self.prev_by_item[curr_item_id] = prev_item_id

        # Link forward pointer for previous, if provided
        if prev_item_id is not None:
            self.next_by_item[prev_item_id] = curr_item_id
            # Ensure prev node exists in maps
            if prev_item_id not in self.prev_by_item:
                self.prev_by_item[prev_item_id] = None
            if prev_item_id not in self.next_by_item:
                self.next_by_item[prev_item_id] = curr_item_id

    def get_timeline_chain_for(self, item_id: models.ItemID) -> list[models.ItemID]:
        """
        Given an item_id (input or response item), walk backwards to the head
        of the chain using prev_by_item, then forward using next_by_item to
        construct the full ordered list of item IDs.
        Returns at least [item_id] if no links exist.
        """
        if not item_id:
            return []
        # Find head
        head = item_id
        while True:
            prev = self.prev_by_item.get(head)
            if prev is None:
                break
            head = prev

        # Walk forward from head
        chain: list[models.ItemID] = []
        curr: Optional[models.ItemID] = head
        visited: set[models.ItemID] = set()
        while curr is not None and curr not in visited:
            chain.append(curr)
            visited.add(curr)
            curr = self.next_by_item.get(curr)
        return chain

    # ---- Convenience lookups ----
    def get_audio_segment(self, item_id: models.ItemID) -> Optional[bytes]:
        markers = self.speech_markers.get(item_id)
        if not markers:
            return None
        start_ms = markers.get("audio_start_ms")
        end_ms = markers.get("audio_end_ms")

        if start_ms is None or end_ms is None:
            return None

        return self.input_audio_buffer.get_segment_ms(start_ms, end_ms)

    # ---- Event application helpers (moved from ConversationManager) ----
    # Session
    def apply_session_created(self, msg: models.SessionCreatedMessage) -> None:
        self.session = msg.session

    def apply_session_updated(self, msg: models.SessionUpdatedMessage) -> None:
        self.session = msg.session

    # Input audio buffer lifecycle
    def apply_input_audio_append(self, msg: models.InputAudioBufferAppendMessage) -> None:
        self.input_audio_buffer.append_base64(msg.audio)

    def apply_input_audio_cleared(self, _msg: models.InputAudioBufferClearedMessage) -> None:
        del _msg
        self.input_audio_buffer.clear()

    def apply_input_audio_committed(self, msg: models.InputAudioBufferCommittedMessage) -> None:
        # Track commits against items for turn completeness checks
        self.committed_item_ids.add(msg.item_id)
        # Wire up linked list pointers if we have a previous item
        prev = getattr(msg, "previous_item_id", None)
        if prev is not None:
            try:
                self.link_items(prev, msg.item_id)
            except Exception:
                pass

    def apply_speech_started(self, msg: models.InputAudioBufferSpeechStartedMessage) -> None:
        self.speech_markers[msg.item_id] = {
            "audio_start_ms": msg.audio_start_ms,
            "audio_end_ms": None,
        }

    def apply_speech_stopped(self, msg: models.InputAudioBufferSpeechStoppedMessage) -> None:
        markers = self.speech_markers.setdefault(msg.item_id, {"audio_start_ms": None, "audio_end_ms": None})
        markers["audio_end_ms"] = msg.audio_end_ms

    # Conversation items
    def apply_item_created(self, msg: models.ItemCreatedMessage) -> None:
        item = msg.item
        self.items[item.id] = item
        self.timeline.append(item.id)
        prev = getattr(msg, "previous_item_id", None)
        if prev is not None:
            try:
                self.link_items(prev, item.id)
            except Exception:
                pass

    def apply_item_truncated(self, _msg: models.ItemTruncatedMessage) -> None:
        # Nothing to change in state beyond markers; leave as-is
        del _msg

    def apply_item_deleted(self, msg: models.ItemDeletedMessage) -> None:
        item = self.items.get(msg.item_id, None)
        if item:
            next_item = self.next_by_item.get(item.id)
            prev_item = self.prev_by_item.get(item.id)

            if next_item and prev_item:
                self.next_by_item[prev_item] = next_item
                self.prev_by_item[next_item] = prev_item
            elif next_item:
                self.prev_by_item[next_item] = None
            elif prev_item:
                self.next_by_item[prev_item] = None

        self.items.pop(msg.item_id, None)
        try:
            self.timeline.remove(msg.item_id)
        except ValueError:
            pass

    def apply_item_input_audio_transcription_delta(self, msg: models.ItemInputAudioTranscriptionDeltaMessage) -> None:
        key = msg.item_id, msg.content_index
        curr = self.input_transcripts.get(key, "")
        self.input_transcripts[key] = curr + msg.delta
        # Mirror into stored item if present
        item = self.items.get(msg.item_id)
        if isinstance(item, (models.ServerUserMessageItem, models.ServerAssistantMessageItem, models.ServerSystemMessageItem)):
            try:
                part = item.content[msg.content_index]
                if isinstance(part, models.InputAudioContentPart):
                    part.transcript = (part.transcript or "") + msg.delta
            except Exception:
                pass

    def apply_item_input_audio_transcription_completed(self, msg: models.ItemInputAudioTranscriptionCompletedMessage) -> None:
        key = (msg.item_id, msg.content_index)
        self.input_transcripts[key] = msg.transcript
        item = self.items.get(msg.item_id)
        if isinstance(item, (models.ServerUserMessageItem, models.ServerAssistantMessageItem, models.ServerSystemMessageItem)):
            try:
                part = item.content[msg.content_index]
                if isinstance(part, models.InputAudioContentPart):
                    part.transcript = msg.transcript
            except Exception:
                pass

    # Responses
    def apply_response_create(self, msg: models.ResponseCreateMessage) -> None:
        ctx: Optional[CustomInputContext] = None
        if msg.response and (msg.response.input_items or msg.response.append_input_items):
            ctx = CustomInputContext(
                input_items=msg.response.input_items,
                append_input_items=msg.response.append_input_items,
            )
        self.pending_custom_context = ctx

    def apply_response_created(self, msg: models.ResponseCreatedMessage) -> None:
        resp = msg.response
        self.responses[resp.id] = resp
        if self.pending_custom_context is not None:
            user_ctx: Union[TimelineContext, CustomInputContext]
            user_ctx = self.pending_custom_context.model_copy()
        else:
            user_ctx = cast(TimelineContext, {"timeline_items": list(self.timeline)})
        self.response_context[resp.id] = {
            "user_context": user_ctx,
            "assistant_context": {"timeline_items": list(self.timeline)},
        }
        self.pending_custom_context = None

    def apply_response_done(self, msg: models.ResponseDoneMessage) -> None:
        self.responses[msg.response.id] = msg.response

    def apply_response_output_item_added(self, msg: models.ResponseOutputItemAddedMessage) -> None:
        resp = self.responses.setdefault(
            msg.response_id,
            models.Response(id=msg.response_id, status="in_progress", status_details=None, output=[], usage=None, conversation_id=None),
        )
        if msg.output_index < len(resp.output):
            resp.output[msg.output_index] = msg.item
        else:
            resp.output.append(msg.item)
        self.items[msg.item.id] = msg.item
        self.response_context.setdefault(msg.response_id, {
            "user_context": {"timeline_items": list(self.timeline)},
            "assistant_context": {"timeline_items": list(self.timeline)},
        })

    def apply_response_output_item_done(self, msg: models.ResponseOutputItemDoneMessage) -> None:
        resp = self.responses.get(msg.response_id)
        if resp is not None and msg.output_index < len(resp.output):
            resp.output[msg.output_index] = msg.item
        self.items[msg.item.id] = msg.item

    def apply_response_content_part_added(self, msg: models.ResponseContentPartAddedMessage) -> None:
        resp = self.responses.get(msg.response_id)
        if not resp:
            logger.warning("apply_response_content_part_added: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
        except StopIteration:
            logger.warning("apply_response_content_part_added: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return
        if isinstance(item, models.ResponseMessageItem):
            while len(item.content) <= msg.content_index:
                item.content.append(msg.part)
        key = (msg.response_id, msg.item_id, msg.content_index)
        if msg.part.type == "text":
            self.resp_text_parts.setdefault(key, "")
        elif msg.part.type == "audio":
            self.resp_audio_transcripts.setdefault(key, "")
            self.resp_audio_bytes.setdefault(key, bytearray())

    def apply_response_content_part_done(self, msg: models.ResponseContentPartDoneMessage) -> None:
        resp = self.responses.get(msg.response_id)
        if not resp:
            logger.warning("apply_response_content_part_done: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
        except StopIteration:
            logger.warning("apply_response_content_part_done: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return
        if isinstance(item, models.ResponseMessageItem):
            while len(item.content) <= msg.content_index:
                item.content.append(msg.part)
            item.content[msg.content_index] = msg.part

    def apply_response_text_delta(self, msg: models.ResponseTextDeltaMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        curr = self.resp_text_parts.get(key, "")
        self.resp_text_parts[key] = curr + msg.delta
        resp = self.responses.get(msg.response_id)
        if not resp:
            logger.warning("apply_response_text_delta: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, models.ResponseMessageItem):
                while len(item.content) <= msg.content_index:
                    item.content.append(models.ResponseItemTextContentPart(type="text", text=""))
                part = item.content[msg.content_index]
                if isinstance(part, models.ResponseItemTextContentPart):
                    part.text = (part.text or "") + msg.delta
        except StopIteration:
            logger.warning("apply_response_text_delta: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return

    def apply_response_text_done(self, msg: models.ResponseTextDoneMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        self.resp_text_parts[key] = msg.text
        resp = self.responses.get(msg.response_id)
        if not resp:
            logger.warning("apply_response_text_done: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, models.ResponseMessageItem):
                while len(item.content) <= msg.content_index:
                    item.content.append(models.ResponseItemTextContentPart(type="text", text=""))
                item.content[msg.content_index] = models.ResponseItemTextContentPart(type="text", text=msg.text)
        except StopIteration:
            logger.warning("apply_response_text_done: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return

    def apply_response_audio_transcript_delta(self, msg: models.ResponseAudioTranscriptDeltaMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        curr = self.resp_audio_transcripts.get(key, "")
        self.resp_audio_transcripts[key] = curr + msg.delta
        resp = self.responses.get(msg.response_id)
        if not resp:
            logger.warning("apply_response_audio_transcript_delta: response not found for response_id=%s", msg.response_id)
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
            logger.warning("apply_response_audio_transcript_delta: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return

    def apply_response_audio_transcript_done(self, msg: models.ResponseAudioTranscriptDoneMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        self.resp_audio_transcripts[key] = msg.transcript
        resp = self.responses.get(msg.response_id)
        if not resp:
            logger.warning("apply_response_audio_transcript_done: response not found for response_id=%s", msg.response_id)
            return
        try:
            item = next(i for i in resp.output if i.id == msg.item_id)
            if isinstance(item, models.ResponseMessageItem):
                while len(item.content) <= msg.content_index:
                    item.content.append(models.ResponseItemAudioContentPart(type="audio", transcript=""))
                item.content[msg.content_index] = models.ResponseItemAudioContentPart(type="audio", transcript=msg.transcript)
        except StopIteration:
            logger.warning("apply_response_audio_transcript_done: item_id=%s not found in response_id=%s output", msg.item_id, msg.response_id)
            return

    def apply_response_audio_delta(self, msg: models.ResponseAudioDeltaMessage) -> None:
        key = (msg.response_id, msg.item_id, msg.content_index)
        buf = self.resp_audio_bytes.setdefault(key, bytearray())
        try:
            buf.extend(base64.b64decode(msg.delta))
        except Exception as e:
            logger.warning(
                "apply_response_audio_delta: failed to base64-decode audio (rid=%s,iid=%s,idx=%s): %s",
                msg.response_id,
                msg.item_id,
                msg.content_index,
                e,
            )

    def apply_response_audio_done(self, _msg: models.ResponseAudioDoneMessage) -> None:
        del _msg
        # No state change; bytes accumulated incrementally

    def apply_response_function_call_arguments_delta(self, msg: models.ResponseFunctionCallArgumentsDeltaMessage) -> None:
        key = (msg.response_id, msg.call_id)
        curr = self.resp_func_args.get(key, "")
        self.resp_func_args[key] = curr + msg.delta

    def apply_response_function_call_arguments_done(self, msg: models.ResponseFunctionCallArgumentsDoneMessage) -> None:
        key = (msg.response_id, msg.call_id)
        self.resp_func_args[key] = msg.arguments
