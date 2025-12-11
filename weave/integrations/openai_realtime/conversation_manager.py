from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from queue import Empty, Queue
from threading import Lock
from typing import TypeVar, cast

logger = logging.getLogger(__name__)
from weave.integrations.openai_realtime import models
from weave.integrations.openai_realtime.state_exporter import StateExporter

T_specific = TypeVar("T_specific", bound=models.MessageType)

# Use a uniform handler type for registry storage. We adapt
# specific handlers (expecting concrete message classes) into this.
Handler = Callable[[models.MessageType], None]


def adapt_handler(cls: type[T_specific], func: Callable[[T_specific], None]) -> Handler:
    """Adapt a concrete-typed handler into a generic registry handler.
    # This preserves runtime safety (checks isinstance before calling) and
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

    def update(self, handlers: dict[str, Handler]) -> None:
        for event, handler in handlers.items():
            self.register(event, handler)

    def get(self, event_type: str) -> Handler | None:
        return self._handlers.get(event_type)


class ConversationManager:
    """Orchestrates event-driven state management for a conversation.
    Provides async queue submission and direct processing.
    """

    def __init__(self) -> None:
        # Optional base URL for downstream export context
        self.client_base_url: str | None = None
        self.state: StateExporter = StateExporter()
        self._registry = EventHandlerRegistry()
        # Worker-thread based event queue + lifecycle
        self._queue: Queue[models.MessageType] = Queue()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._lock = Lock()

        handlers: dict[str, Handler] = {
            # Session lifecycle
            "session.created": adapt_handler(
                models.SessionCreatedMessage, self.state.handle_session_created
            ),
            "session.update": adapt_handler(
                models.SessionUpdateMessage, self.state.handle_session_update
            ),
            "session.updated": adapt_handler(
                models.SessionUpdatedMessage, self.state.handle_session_updated
            ),
            # Input audio buffer lifecycle
            "input_audio_buffer.append": adapt_handler(
                models.InputAudioBufferAppendMessage,
                self.state.handle_input_audio_append,
            ),
            "input_audio_buffer.cleared": adapt_handler(
                models.InputAudioBufferClearedMessage,
                self.state.handle_input_audio_cleared,
            ),
            "input_audio_buffer.committed": adapt_handler(
                models.InputAudioBufferCommittedMessage,
                self.state.handle_input_audio_committed,
            ),
            "input_audio_buffer.speech_started": adapt_handler(
                models.InputAudioBufferSpeechStartedMessage,
                self.state.handle_speech_started,
            ),
            "input_audio_buffer.speech_stopped": adapt_handler(
                models.InputAudioBufferSpeechStoppedMessage,
                self.state.handle_speech_stopped,
            ),
            # Conversation item changes
            "conversation.item.created": adapt_handler(
                models.ItemCreatedMessage, self.state.handle_item_created
            ),
            "conversation.item.deleted": adapt_handler(
                models.ItemDeletedMessage, self.state.handle_item_deleted
            ),
            "conversation.item.input_audio_transcription.completed": adapt_handler(
                models.ItemInputAudioTranscriptionCompletedMessage,
                self.state.handle_item_input_audio_transcription_completed,
            ),
            # Response lifecycle and parts
            "response.created": adapt_handler(
                models.ResponseCreatedMessage, self.state.handle_response_created
            ),
            "response.done": adapt_handler(
                models.ResponseDoneMessage, self.state.handle_response_done
            ),
            "response.audio.delta": adapt_handler(
                models.ResponseAudioDeltaMessage, self.state.handle_response_audio_delta
            ),
            "response.audio.done": adapt_handler(
                models.ResponseAudioDoneMessage, self.state.handle_response_audio_done
            ),
        }

        self._registry.update(handlers)
        # Start the worker thread immediately so enqueue works out of the box
        self._start_worker_thread()

    async def start(self) -> None:
        """Async-compatible start that spins up the worker thread."""
        self._start_worker_thread()

    async def stop(self) -> None:
        """Async-compatible stop that signals the worker thread to exit."""
        self._stop_worker_thread()

    def _start_worker_thread(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        t = threading.Thread(
            target=self._worker, name="ConversationManagerWorker", daemon=True
        )
        t.start()
        self._worker_thread = t

    def _stop_worker_thread(self) -> None:
        if self._worker_thread is None:
            return
        self._stop_event.set()
        # Wake the thread if it's blocked waiting for an item
        self._queue.put_nowait(cast(models.MessageType, None))  # type: ignore[arg-type]
        # Don't block indefinitely; thread is daemon and will also exit on main-thread exit
        self._worker_thread.join(timeout=1.0)
        self._worker_thread = None

    def _worker(self) -> None:
        """Worker loop running in a daemon thread, draining events from the queue.

        Exits when `_stop_event` is set or when the main thread exits (daemon=True).
        """
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=0.1)
            except Empty:
                continue
            # Sentinel to unblock during shutdown
            if event is None:
                try:
                    self._queue.task_done()
                except ValueError:
                    pass
                continue
            try:
                self.process_event(event)
            finally:
                try:
                    self._queue.task_done()
                except ValueError:
                    # If task_done called more times than items; guard against misuse
                    pass

    async def submit_event(self, event: models.MessageType) -> None:
        """Async-compatible enqueue; places the event onto the worker queue."""
        self._queue.put(event)

    def process_event(self, event: models.MessageType) -> None:
        """Process an event synchronously"""
        # Event objects have a 'type' field in pydantic models.
        event_type = getattr(event, "type", None)
        if not event_type:
            return

        handler = self._registry.get(event_type)
        if handler:
            with self._lock:
                handler(event)
