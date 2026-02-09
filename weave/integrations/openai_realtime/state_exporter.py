from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, Self

from pydantic import BaseModel, Field

from weave.integrations.openai_realtime.audio_buffer import AudioBufferManager
from weave.integrations.openai_realtime.encoding import pcm_to_wav
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.weave_client import Call
from weave.type_wrappers.Content import Content

logger = logging.getLogger(__name__)


class SessionSpan(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    root_call: Call | None = None
    last_update: Call | Callable[[Call], Call] | None = None
    session: dict | None = None

    def get_root_call(self) -> Call | None:
        return self.root_call

    def get_session(self) -> dict | None:
        return self.session

    @classmethod
    def from_session(cls, session: dict | None = None) -> Self:
        root_call = None
        if session:
            wc = require_weave_client()
            root_call = wc.create_call("realtime.session", inputs=session)
        inst = cls(session=session, root_call=root_call)
        return inst

    def on_created(self, msg: dict) -> None:
        self.session = msg.get("session")
        if not self.session or not isinstance(self.session, dict):
            self.session = {}
        wc = require_weave_client()
        if not self.root_call:
            self.root_call = wc.create_call("realtime.session", inputs=self.session)

    def on_updated(self, msg: dict) -> None:
        self.session = msg.get("session")
        if not self.session or not isinstance(self.session, dict):
            self.session = {}

        wc = require_weave_client()

        if not self.root_call:
            self.root_call = wc.create_call("realtime.session", inputs=self.session)

        # Return after confirming initialization if we can't properly complete
        if not self.last_update:
            return

        if not self.root_call:
            logger.error("Missing session in on_updated - this should never occur")
            self.last_update = None
            return

        if not isinstance(self.last_update, Call):
            call = self.last_update(self.root_call)
        else:
            call = self.last_update
        wc.finish_call(call, output=self.session)
        self.last_update = None

    def on_update(self, msg: dict) -> None:
        self.session = msg.get("session")
        wc = require_weave_client()
        if not self.session or not self.session.get("id"):
            # Registered a CB since updated will run after created
            def update_cb(root_call: Call) -> Call:
                return wc.create_call(
                    "realtime.session.update",
                    inputs=self.session,  # type: ignore
                    parent=root_call,
                )

            self.last_update = update_cb
        else:
            self.last_update = wc.create_call(
                "realtime.session.update",
                inputs=self.session,
                parent=self.root_call,
            )


class ItemRegistry:
    speech_markers: dict[str, dict[str, int | None]] = Field(default_factory=dict)
    input_audio_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)

    # ---- Convenience lookups ----
    def get_audio_segment(self, item_id: str) -> bytes | None:
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
    session_span: SessionSpan | None = None
    # Map conversation -> response ids
    conversation_responses: dict[str, list[str]] = Field(default_factory=dict)
    # Map conversation -> call
    conversation_calls: dict[str, Call] = Field(default_factory=dict)
    timeline: list[str] = Field(default_factory=list)
    committed_item_ids: set[str] = Field(default_factory=set)

    transcript_completed: set[str] = Field(default_factory=set)
    items: dict[str, dict] = Field(default_factory=dict)
    last_input_item_id: str | None = None

    prev_by_item: dict[str, str | None] = Field(default_factory=dict)
    next_by_item: dict[str, str | None] = Field(default_factory=dict)

    input_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)
    output_buffer: AudioBufferManager = Field(default_factory=AudioBufferManager)

    user_messages: dict[str, dict] = Field(default_factory=dict)
    user_speech_markers: dict[str, dict[str, int | None]] = Field(default_factory=dict)

    response_audio: dict[str, bytes] = Field(default_factory=dict)
    response_calls: dict[str, Call] = Field(default_factory=dict)
    responses: dict[str, dict] = Field(default_factory=dict)
    # Deprecated: per-response debounce timers caused out-of-order completions
    debounce_timers: dict[str, threading.Timer] = Field(default_factory=dict)

    # FIFO completion control to ensure responses finish in submission order
    completion_queue: list[str] = Field(default_factory=list)
    pending_completions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    fifo_timer: threading.Timer | None = None
    fifo_lock: threading.Lock = Field(default_factory=threading.Lock)

    pending_response: dict | None = None
    pending_create_params: dict | None = None

    def __init__(self) -> None:
        super().__init__()

    def _get_item_audio(self, item_id: str) -> bytes | None:
        markers = self.user_speech_markers.get(item_id)
        if not markers:
            return None
        start_ms = markers.get("audio_start_ms")
        end_ms = markers.get("audio_end_ms")

        if start_ms is None or end_ms is None:
            return None
        return self.input_buffer.get_segment_ms(start_ms, end_ms)

    def handle_session_created(self, msg: dict) -> None:
        session = msg.get("session")
        if not self.session_span:
            self.session_span = SessionSpan.from_session(session)
        self.session_span.on_created(msg)

    def handle_session_update(self, msg: dict) -> None:
        if not self.session_span:
            self.session_span = SessionSpan()
        self.session_span.on_update(msg)

    def handle_session_updated(self, msg: dict) -> None:
        session = msg.get("session")
        if not self.session_span:
            self.session_span = SessionSpan.from_session(session)
        self.session_span.on_updated(msg)

    def handle_speech_stopped(self, msg: dict) -> None:
        item_id = msg.get("item_id", "")
        markers = self.user_speech_markers.setdefault(
            item_id, {"audio_start_ms": None, "audio_end_ms": None}
        )
        markers["audio_end_ms"] = msg.get("audio_end_ms")

    def handle_speech_started(self, msg: dict) -> None:
        item_id = msg.get("item_id", "")
        self.user_speech_markers[item_id] = {
            "audio_start_ms": msg.get("audio_start_ms"),
            "audio_end_ms": None,
        }

    def handle_item_created(self, msg: dict) -> None:
        item = msg.get("item") or {}
        item_id = item.get("id")
        if item_id:
            previous_item_id = msg.get("previous_item_id")
            self.prev_by_item[item_id] = previous_item_id
            if previous_item_id and self.items.get(previous_item_id):
                self.next_by_item[previous_item_id] = item_id
            self.items[item_id] = item
            self.last_input_item_id = item_id

    def handle_item_deleted(self, msg: dict) -> None:
        item_id = msg.get("item_id")
        item = self.items.get(item_id) if item_id else None
        if item and item_id:
            next_item = self.next_by_item.get(item_id)
            prev_item = self.prev_by_item.get(item_id)

            if next_item and prev_item:
                self.next_by_item[prev_item] = next_item
                self.prev_by_item[next_item] = prev_item
            elif next_item:
                self.prev_by_item[next_item] = None
            elif prev_item:
                self.next_by_item[prev_item] = None

        if item_id:
            self.items.pop(item_id, None)
            try:
                self.timeline.remove(item_id)
            except ValueError:
                pass

    def handle_input_audio_cleared(self, _: dict) -> None:
        self.input_buffer.clear()

    def handle_input_audio_committed(self, msg: dict) -> None:
        item_id = msg.get("item_id")
        if item_id:
            self.committed_item_ids.add(item_id)
            previous_item_id = msg.get("previous_item_id")
            if previous_item_id:
                self.next_by_item[previous_item_id] = item_id
                self.prev_by_item[item_id] = previous_item_id

    def handle_response_created(self, msg: dict) -> None:
        self.pending_response = msg.get("response")

    def handle_input_audio_append(self, msg: dict) -> None:
        audio = msg.get("audio")
        if audio:
            self.input_buffer.extend_base64(audio)

    def handle_response_audio_delta(self, msg: dict) -> None:
        delta = msg.get("delta")
        if delta:
            self.output_buffer.extend_base64(delta)

    def handle_response_audio_done(self, msg: dict) -> None:
        item_id = msg.get("item_id")
        if item_id:
            self.response_audio[item_id] = bytes(self.output_buffer.buffer)
        self.output_buffer.clear()

    def _response_with_audio(self, resp: dict) -> dict[str, Any]:
        response_dict = dict(resp)
        output_list = resp.get("output", [])
        for output_idx, output in enumerate(output_list):
            output_type = output.get("type")
            if output_type in ("function_call", "function_call_output"):
                continue
            content_list = output.get("content", [])
            for content_idx, content in enumerate(content_list):
                content_type = content.get("type")
                if content_type in ("audio", "output_audio"):
                    output_id = output.get("id")
                    audio = self.response_audio.get(output_id) if output_id else None
                    if not audio:
                        continue
                    response_dict["output"][output_idx]["content"][content_idx][
                        "audio"
                    ] = Content.from_bytes(pcm_to_wav(audio), extension=".wav")
        return response_dict

    def _get_input_item_list(self, output: list[dict]) -> list[dict]:
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
        item_id = item.get("id") if isinstance(item, dict) else None
        prev_id = self.prev_by_item.get(item_id) if item_id else None
        inputs: list[dict] = []
        if not prev_id:
            return inputs
        prev_item = self.items.get(prev_id)
        while prev_id and prev_item:
            inputs.append(prev_item)
            prev_item_id = prev_item.get("id") if isinstance(prev_item, dict) else None
            prev_id = self.prev_by_item.get(prev_item_id) if prev_item_id else None
            if not prev_id:
                break
            prev_item = self.items.get(prev_id)
        return inputs

    def handle_item_input_audio_transcription_completed(self, msg: dict) -> None:
        item_id = msg.get("item_id")
        if not item_id:
            return
        item = self.items.get(item_id)
        if not item:
            return
        content_index = msg.get("content_index")
        transcript = msg.get("transcript")
        if content_index is not None and isinstance(item.get("content"), list):
            content_list = item["content"]
            if content_index < len(content_list):
                content_list[content_index]["transcript"] = transcript
        self.items[item_id] = item
        self.transcript_completed.add(item_id)
        self._schedule_fifo_check()

    def _resolve_audio(self, msg: dict) -> Any:
        msg_type = msg.get("type")
        if msg_type != "message":
            return msg
        msg_dict = dict(msg)
        item_id = msg.get("id")
        content_list = msg.get("content", [])
        for content_idx, content in enumerate(content_list):
            audio = None
            content_type = content.get("type")
            if content_type == "input_audio":
                audio = self._get_item_audio(item_id) if item_id else None
            elif content_type in ("audio", "output_audio"):
                audio = self.response_audio.get(item_id) if item_id else None

            if not audio:
                continue
            audio = pcm_to_wav(audio)
            msg_dict["content"][content_idx]["audio"] = Content.from_bytes(
                audio, extension=".wav"
            )

        return msg_dict

    def _handle_response_done_inner(
        self,
        msg: dict,
        session: dict | None = None,
        pending_create_params: dict | None = None,
        messages: list[dict] | None = None,
    ) -> None:
        """Note: This is pretty ugly but it achieves something that is worth the bloat.
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

        if pending_create_params and (
            items := pending_create_params.get("input_items")
        ):
            for item in items:
                inputs["messages"].append(item)

        if pending_create_params and (
            items := pending_create_params.get("append_input_items")
        ):
            for item in items:
                inputs["messages"].append(item)

        if pending_create_params is not None:
            inputs.update(pending_create_params)
            pending_create_params = None

        if session:
            inputs.update(session)

        from weave.trace.context.weave_client_context import require_weave_client

        client = require_weave_client()

        session_call = None
        if self.session_span:
            session_call = self.session_span.get_root_call()

        response_parent = None

        response = msg.get("response", {})
        conv_id = response.get("conversation_id")
        response_id = response.get("id")
        if conv_id and self.conversation_responses.get(conv_id) is not None:
            if response_id:
                self.conversation_responses[conv_id].append(response_id)
        elif conv_id and response_id:
            self.conversation_responses[conv_id] = [response_id]

        if conv_id and (conv_call := self.conversation_calls.get(conv_id)):
            response_parent = conv_call
        elif conv_id:
            conv_call = client.create_call(
                op="realtime.conversation", inputs={"id": conv_id}, parent=session_call
            )
            self.conversation_calls[conv_id] = conv_call
            response_parent = conv_call
        else:
            response_parent = session_call

        call = client.create_call(
            "realtime.response", inputs=inputs, parent=response_parent
        )

        output_dict = dict(response)
        output_list = response.get("output", [])
        for output_idx, output in enumerate(output_list):
            if output.get("type") == "message":
                item_id = output.get("id")
                content_list = output.get("content", [])
                for content_idx, content in enumerate(content_list):
                    content_dict = dict(content)
                    content_type = content.get("type")
                    if content_type in ("audio", "output_audio"):
                        audio_bytes = (
                            self.response_audio.get(item_id) if item_id else None
                        )
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

    def handle_response_done(self, msg: dict) -> None:
        response = msg.get("response", {})
        response_id = response.get("id")
        if response_id:
            self.responses[response_id] = response
        for item in response.get("output", []):
            item_id = item.get("id")
            if item_id:
                self.items[item_id] = item

        pending_create_params = self.pending_create_params
        pending_response = self.pending_response

        if pending_response is None:
            logger.error("Attempted to finish response that was never created")
            return

        messages = self._get_input_item_list(response.get("output", []))

        ctx: dict[str, Any] = {
            "msg": msg,
            "session": self.session_span.get_session() if self.session_span else None,
            "pending_create_params": pending_create_params,
            "pending_response": pending_response,
            "messages": messages,
        }

        with self.fifo_lock:
            if response_id:
                self.pending_completions[response_id] = ctx
                if response_id not in self.completion_queue:
                    self.completion_queue.append(response_id)

        self._schedule_fifo_check()

    def _transcripts_ready_for_ctx(self, ctx: dict[str, Any]) -> bool:
        session = ctx.get("session")
        messages = ctx.get("messages", [])
        modalities = session.get("modalities", []) if isinstance(session, dict) else []
        if session and "text" in modalities:
            for message in messages:
                msg_id = message.get("id") if isinstance(message, dict) else None
                if (
                    message.get("type") == "message"
                    and message.get("role") == "user"
                    and msg_id not in self.transcript_completed
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
            msg = ctx["msg"]
            self._handle_response_done_inner(
                msg,
                ctx.get("session"),
                ctx.get("pending_create_params"),
                ctx.get("messages", []),
            )

            # Remove the head and continue to next (if it's immediately ready)
            with self.fifo_lock:
                rid = msg.get("response", {}).get("id")
                if rid and self.completion_queue and self.completion_queue[0] == rid:
                    self.completion_queue.pop(0)
                if rid:
                    self.pending_completions.pop(rid, None)

            # Loop to see if the next head is already ready; otherwise schedule check
            # for later and return.
            # The loop continues only if the immediate next is also ready now.
            continue

    def build_conversation_forward(self, item_id: str) -> list[dict]:
        item = self.items.get(item_id)
        if not item:
            return []

        items = [item]
        next_item_id = self.next_by_item.get(item_id)

        if not next_item_id:
            return items

        while item:
            if not next_item_id:
                break
            item = self.items.get(next_item_id)
            if not item:
                break
            items.append(item)
            item_id = item.get("id") if isinstance(item, dict) else None
            next_item_id = self.next_by_item.get(item_id) if item_id else None
        return items

    def on_exit(self) -> None:
        wc = require_weave_client()
        if self.session_span and self.session_span.root_call:
            # Complete it with the final state of the session
            wc.finish_call(
                self.session_span.root_call, output=self.session_span.session
            )

        for call in self.conversation_calls.values():
            conv_id = call.inputs["id"]
            if responses := self.conversation_responses.get(conv_id):
                num_responses = len(responses)
            else:
                num_responses = 0

            wc.finish_call(call, output={"num_responses": num_responses})
