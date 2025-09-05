import logging
import threading
from typing import Any, Optional, Union, cast

from pydantic import BaseModel, Field

from weave.integrations.openai_realtime import models
from weave.integrations.openai_realtime.audio_buffer import AudioBufferManager
from weave.integrations.openai_realtime.encoding import pcm_to_wav
from weave.trace.weave_client import Call
from weave.type_wrappers.Content import Content

logger = logging.getLogger(__name__)

DeltaMessage = Union[
    models.ResponseTextDeltaMessage,
    models.ResponseAudioDeltaMessage,
    models.ResponseAudioTranscriptDeltaMessage,
    models.ResponseFunctionCallArgumentsDeltaMessage,
]
StoredItem = Union[models.ServerItem, models.ResponseItem]


class ItemRegistry:
    speech_markers: dict[models.ItemID, dict[str, Optional[int]]] = Field(
        default_factory=dict
    )
    input_audio_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)

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


class StateExporter(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    session: Optional[models.Session] = None
    conversation_calls: dict[models.ConversationID, Call] = Field(default_factory=dict)
    timeline: list[Union[models.ItemID, models.ResponseID]] = Field(
        default_factory=list
    )
    committed_item_ids: set[models.ItemID] = Field(default_factory=set)

    transcript_completed: set[models.ItemID] = Field(default_factory=set)
    items: dict[models.ItemID, Union[models.ServerItem, models.ResponseItem]] = Field(
        default_factory=dict
    )
    last_input_item_id: Optional[models.ItemID] = (
        None  # Last message item not generated as part ofa response
    )

    prev_by_item: dict[models.ItemID, Optional[models.ItemID]] = Field(
        default_factory=dict
    )
    next_by_item: dict[models.ItemID, Optional[models.ItemID]] = Field(
        default_factory=dict
    )

    input_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)
    output_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)

    user_messages: dict[models.ItemID, models.ClientUserMessageItem] = Field(
        default_factory=dict
    )  # For efficiency we don't convert back to base64
    user_speech_markers: dict[models.ItemID, dict[str, Optional[int]]] = Field(
        default_factory=dict
    )

    response_audio: dict[models.ItemID, bytes] = Field(default_factory=dict)
    response_calls: dict[models.ResponseID, Call] = Field(default_factory=dict)
    responses: dict[models.ResponseID, models.Response] = Field(default_factory=dict)
    # Deprecated: per-response debounce timers caused out-of-order completions
    debounce_timers: dict[models.ResponseID, threading.Timer] = {}

    # FIFO completion control to ensure responses finish in submission order
    completion_queue: list[models.ResponseID] = Field(default_factory=list)
    pending_completions: dict[models.ResponseID, dict[str, Any]] = Field(
        default_factory=dict
    )
    fifo_timer: Optional[threading.Timer] = None
    fifo_lock: threading.Lock = Field(default_factory=threading.Lock)

    pending_response: Optional[models.Response] = None
    pending_create_params: Optional[models.ResponseCreateParams] = None

    def __init__(self) -> None:
        super().__init__()

    def _get_item_audio(self, item_id: models.ItemID) -> Optional[bytes]:
        markers = self.user_speech_markers.get(item_id)
        if not markers:
            return None
        start_ms = markers.get("audio_start_ms")
        end_ms = markers.get("audio_end_ms")

        if start_ms is None or end_ms is None:
            return None
        return self.input_buffer.get_segment_ms(start_ms, end_ms)

    def handle_session_created(self, msg: models.SessionCreatedMessage) -> None:
        self.session = msg.session

    def handle_session_updated(self, msg: models.SessionUpdatedMessage) -> None:
        self.session = msg.session

    def handle_speech_stopped(
        self, msg: models.InputAudioBufferSpeechStoppedMessage
    ) -> None:
        markers = self.user_speech_markers.setdefault(
            msg.item_id, {"audio_start_ms": None, "audio_end_ms": None}
        )
        markers["audio_end_ms"] = msg.audio_end_ms

    def handle_speech_started(
        self, msg: models.InputAudioBufferSpeechStartedMessage
    ) -> None:
        self.user_speech_markers[msg.item_id] = {
            "audio_start_ms": msg.audio_start_ms,
            "audio_end_ms": None,
        }

    def handle_item_created(self, msg: models.ItemCreatedMessage) -> None:
        item = msg.item
        self.prev_by_item[item.id] = msg.previous_item_id
        if msg.previous_item_id and self.items.get(msg.previous_item_id):
            self.next_by_item[msg.previous_item_id] = item.id
        self.items[item.id] = item
        self.last_input_item_id = item.id

    def handle_item_deleted(self, msg: models.ItemDeletedMessage) -> None:
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

    def handle_input_audio_cleared(
        self, _: models.InputAudioBufferClearedMessage
    ) -> None:
        self.input_buffer.clear()

    def handle_input_audio_committed(
        self, msg: models.InputAudioBufferCommittedMessage
    ) -> None:
        # Track commits against items for turn completeness checks
        self.committed_item_ids.add(msg.item_id)
        if msg.previous_item_id:
            self.next_by_item[msg.previous_item_id] = msg.item_id
            self.prev_by_item[msg.item_id] = msg.item_id

    def handle_response_created(self, msg: models.ResponseCreatedMessage) -> None:
        self.pending_response = msg.response

    def handle_input_audio_append(
        self, msg: models.InputAudioBufferAppendMessage
    ) -> None:
        self.input_buffer.extend_base64(msg.audio)

    def handle_response_audio_delta(
        self, msg: models.ResponseAudioDeltaMessage
    ) -> None:
        self.output_buffer.extend_base64(msg.delta)

    def handle_response_audio_done(self, msg: models.ResponseAudioDoneMessage) -> None:
        self.response_audio[msg.item_id] = bytes(self.output_buffer.buffer)
        self.output_buffer.clear()

    def _response_with_audio(self, resp: models.Response) -> dict[str, Any]:
        response_dict = resp.model_dump()
        for output_idx, output in enumerate(resp.output):
            if output.type == "function_call" or output.type == "function_call_output":
                continue
            for content_idx, content in enumerate(output.content):
                if content.type == "audio":
                    audio = self.response_audio.get(output.id)
                    if not audio:
                        continue
                    response_dict["output"][output_idx]["content"][content_idx][
                        "audio"
                    ] = Content.from_bytes(pcm_to_wav(audio), extension=".wav")
        return response_dict

    def _get_input_item_list(
        self, output: list[models.ResponseItem]
    ) -> list[Union[models.ResponseItem, models.ServerItem]]:
        if len(output) > 1:
            logger.error("Inputs for multi-output responses are not yet supported")
            return []
        elif len(output) == 0 and self.last_input_item_id:
            item = self.items.get(self.last_input_item_id)
            if not item:
                return []
        elif len(output) == 0:
            return []
        else:
            item = output[0]
        prev_id = self.prev_by_item.get(item.id)
        inputs: list[Union[models.ResponseItem, models.ServerItem]] = []
        if not prev_id:
            return inputs
        prev_item = self.items.get(prev_id)
        while prev_id and prev_item:
            inputs.append(prev_item)
            prev_id = self.prev_by_item.get(prev_item.id)
            if not prev_id:
                break
            prev_item = self.items.get(prev_id)
        return inputs

    def handle_item_input_audio_transcription_completed(
        self, msg: models.ItemInputAudioTranscriptionCompletedMessage
    ) -> None:
        key = msg.item_id
        item = self.items.get(key)
        if not item:
            return
        if isinstance(
            item,
            (
                models.ServerUserMessageItem,
                models.ServerAssistantMessageItem,
                models.ServerSystemMessageItem,
            ),
        ) and isinstance(item.content[msg.content_index], models.InputAudioContentPart):
            item.content[msg.content_index].__setattr__("transcript", msg.transcript)
        self.items[item.id] = item
        self.transcript_completed.add(item.id)
        # A transcript becoming available may unblock the head of the FIFO
        self._schedule_fifo_check()

    def _resolve_audio(self, msg: Union[models.ResponseItem, models.ServerItem]) -> Any:
        if not msg.type == "message":
            return msg.model_dump()
        msg_dict = msg.model_dump()
        for content_idx, content in enumerate(msg.content):
            item_id = msg.id
            audio = None
            if content.type == "input_audio":
                audio = self._get_item_audio(item_id)
            elif content.type == "audio":
                audio = self.response_audio[item_id]

            if not audio:
                return msg_dict
            audio = pcm_to_wav(audio)
            msg_dict["content"][content_idx]["audio"] = Content.from_bytes(
                audio, extension=".wav"
            )

        return msg_dict

    def _handle_response_done_inner(
        self,
        msg: models.ResponseDoneMessage,
        session: Optional[models.Session] = None,
        pending_create_params: Optional[models.ResponseCreateParams] = None,
        messages: Optional[list[Union[models.ResponseItem, models.ServerItem]]] = None,
    ) -> None:
        """
        Note: This is pretty ugly but it achieves something that is worth the bloat.
        Transcription results can occur far after a response to audio is received.
        If we do not wait for them, then you will never see the transcript of your most recent item
        This would mean that for the last turn in the conversation, the transcript goes missing

        The fix would be to add the ability to modify the inputs of a function for our client
        but even that is a bit of a hack since the real issue is that there isn't a true
        "input" "output" paradigm here. Each event sent can spawn dozens in return

        Really transcription is an "output" but implementing that association would require an entirely
        new data model
        """
        inputs: dict[str, Any] = {}
        if messages:
            inputs["messages"] = list(map(self._resolve_audio, messages))
            inputs["messages"].reverse()  # Reverse to put in order

        if pending_create_params and pending_create_params.input_items:
            for item in pending_create_params.input_items:
                inputs["messages"].append(item)

        if pending_create_params and pending_create_params.append_input_items:
            for item in pending_create_params.append_input_items:
                inputs["messages"].append(item)

        if pending_create_params is not None:
            inputs.update(pending_create_params.model_dump())
            pending_create_params = None

        from weave.trace.context.weave_client_context import require_weave_client

        client = require_weave_client()

        resp_id = msg.response.id
        # conv_id = msg.response.conversation_id
        if session:
            inputs.update(session.model_dump())

        # Disable parent call for now since we don't have a way to populate it up
        # conv_call = None
        # if conv_id:
        #     conv_call = self.conversation_calls.get(conv_id)
        #     if not conv_call:
        #         conv_call = client.create_call(op=conv_id, inputs={})
        #         self.conversation_calls[conv_id] = conv_call
        call = client.create_call(resp_id, inputs=inputs, parent=None)

        output_dict = msg.response.model_dump()
        for output_idx, output in enumerate(msg.response.output):
            if output.type == "message":
                item_id = output.id
                for content_idx, content in enumerate(output.content):
                    content_dict = content.model_dump()
                    if content.type == "audio":
                        content_dict = output.content[content_idx].model_dump()
                        audio_bytes = self.response_audio[item_id]
                        if not audio_bytes:
                            logger.error("failed to fetch audio bytes")
                            continue
                        content_dict["audio"] = Content.from_bytes(
                            pcm_to_wav(bytes(audio_bytes)), extension=".wav"
                        )
                    output_dict["output"][output_idx]["content"][content_idx] = (
                        content_dict
                    )
        client.finish_call(call, output=output_dict)

    def handle_response_done(self, msg: models.ResponseDoneMessage) -> None:
        # Update state to the completed version and enqueue for FIFO completion.
        self.responses[msg.response.id] = msg.response
        for item in msg.response.output:
            self.items[item.id] = item

        session = None
        if self.session:
            session = self.session.model_copy()

        pending_create_params = self.pending_create_params
        pending_response = self.pending_response

        if pending_response is None:
            logger.error("Attempted to finish response that was never created")
            return

        messages = self._get_input_item_list(msg.response.output)

        # Store the prepared context for this response id
        ctx: dict[str, Any] = {
            "msg": msg,
            "session": session,
            "pending_create_params": pending_create_params,
            "pending_response": pending_response,
            "messages": messages,
        }

        with self.fifo_lock:
            rid = msg.response.id
            self.pending_completions[rid] = ctx
            if rid not in self.completion_queue:
                self.completion_queue.append(rid)

        # Check if we can advance the FIFO now or schedule retries
        self._schedule_fifo_check()

    def _transcripts_ready_for_ctx(self, ctx: dict[str, Any]) -> bool:
        session = ctx.get("session")
        messages = ctx.get("messages", [])
        if session and "text" in getattr(session, "modalities", []):
            for message in messages:
                if (
                    getattr(message, "type", None) == "message"
                    and getattr(message, "role", None) == "user"
                    and getattr(message, "id", None) not in self.transcript_completed
                ):
                    return False
        return True

    def _schedule_fifo_check(self) -> None:
        """Schedule a short-latency check to advance FIFO completion.

        Uses a single timer to avoid racing multiple callbacks and to ensure
        completions occur strictly in submission order.
        """
        with self.fifo_lock:
            # Cancel an existing timer to coalesce checks
            if self.fifo_timer is not None:
                try:
                    self.fifo_timer.cancel()
                except Exception:
                    pass

            def _cb() -> None:
                try:
                    self._advance_fifo()
                finally:
                    # If more remain and head not ready, a new timer will be scheduled
                    pass

            self.fifo_timer = threading.Timer(0.05, _cb)
            self.fifo_timer.start()

    def _advance_fifo(self) -> None:
        """Attempt to finish the head response if ready; maintain order."""
        while True:
            with self.fifo_lock:
                if not self.completion_queue:
                    # Nothing pending
                    self.fifo_timer = None
                    return
                head = self.completion_queue[0]
                ctx = self.pending_completions.get(head)
                if ctx is None:
                    # Corrupt entry; drop and continue
                    self.completion_queue.pop(0)
                    continue

                ready = self._transcripts_ready_for_ctx(ctx)

            if not ready:
                # Head not ready; reschedule a check and exit to preserve order
                self._schedule_fifo_check()
                return

            # Finish the head outside the lock to avoid blocking
            msg = cast(models.ResponseDoneMessage, ctx["msg"])
            self._handle_response_done_inner(
                msg,
                ctx.get("session"),
                ctx.get("pending_create_params"),
                ctx.get("messages", []),
            )

            # Remove the head and continue to next (if it's immediately ready)
            with self.fifo_lock:
                rid = cast(models.ResponseID, msg.response.id)
                if self.completion_queue and self.completion_queue[0] == rid:
                    self.completion_queue.pop(0)
                self.pending_completions.pop(rid, None)

            # Loop to see if the next head is already ready; otherwise schedule check
            # for later and return.
            # The loop continues only if the immediate next is also ready now.
            continue
