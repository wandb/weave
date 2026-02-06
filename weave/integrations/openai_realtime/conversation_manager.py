from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from queue import Empty, Queue
from threading import Lock

logger = logging.getLogger(__name__)
from weave.integrations.openai_realtime.state_exporter import StateExporter

Handler = Callable[[dict], None]


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
        self._queue: Queue[dict] = Queue()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._lock = Lock()

        handlers: dict[str, Handler] = {
            # Session lifecycle
            "session.created": self.state.handle_session_created,
            "session.update": self.state.handle_session_update,
            "session.updated": self.state.handle_session_updated,
            # Input audio buffer lifecycle
            "input_audio_buffer.append": self.state.handle_input_audio_append,
            "input_audio_buffer.cleared": self.state.handle_input_audio_cleared,
            "input_audio_buffer.committed": self.state.handle_input_audio_committed,
            "input_audio_buffer.speech_started": self.state.handle_speech_started,
            "input_audio_buffer.speech_stopped": self.state.handle_speech_stopped,
            # Conversation item changes
            "conversation.item.created": self.state.handle_item_created,
            "conversation.item.deleted": self.state.handle_item_deleted,
            "conversation.item.input_audio_transcription.completed": self.state.handle_item_input_audio_transcription_completed,
            # Response lifecycle and parts
            "response.created": self.state.handle_response_created,
            "response.done": self.state.handle_response_done,
            "response.audio.delta": self.state.handle_response_audio_delta,
            "response.audio.done": self.state.handle_response_audio_done,
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
        self._queue.put_nowait(None)
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

    async def submit_event(self, event: dict) -> None:
        """Async-compatible enqueue; places the event onto the worker queue."""
        self._queue.put(event)

    def process_event(self, event: dict) -> None:
        """Process an event synchronously"""
        event_type = event.get("type")
        if not event_type:
            return

        handler = self._registry.get(event_type)
        if handler:
            with self._lock:
                handler(event)
