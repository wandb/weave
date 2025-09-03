import logging
import base64
from dataclasses import dataclass, field
from typing import Optional, Union
from typing_extensions import Iterable, TypedDict
from pydantic import BaseModel, Field
from weave.integrations.openai_realtime import models

logger = logging.getLogger(__name__)

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
        except Exception as e:
            # Some fixtures use placeholder strings like "<audio bytes>".
            # Skip invalid base64 without failing the pipeline, but log for visibility.
            logger.warning("AudioBufferManager.append_base64: invalid base64; ignoring. error=%s preview=%r", e, b64[:20])

    def clear(self) -> None:
        self.buffer.clear()

    def _ms_to_byte_range(self, start_ms: int, end_ms: int) -> tuple[int, int]:
        bps = self.bytes_per_sample()
        start_samples = int((start_ms / 1000.0) * self.sample_rate_hz)
        end_samples = int((end_ms / 1000.0) * self.sample_rate_hz)
        return start_samples * bps, end_samples * bps

    def get_segment_ms(self, start_ms: int, end_ms: int) -> bytes:
        start_b, end_b = self._ms_to_byte_range(start_ms, end_ms)
        start_b = max(0, start_b)
        end_b = min(len(self.buffer), max(start_b, end_b))
        return bytes(self.buffer[start_b:end_b])


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

    # Map from an input item (previous item in output chain) -> response id
    # This is populated on response completion, using the prev linkage for any
    # output items observed in that response.
    response_by_prev_item: dict[models.ItemID, models.ResponseID] = Field(default_factory=dict)

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
