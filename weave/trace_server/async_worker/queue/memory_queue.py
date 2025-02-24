"""
In-memory queue implementation with exactly-once delivery semantics.
This implementation is intended for development and testing purposes.
"""

import queue
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional

from .queue_interface import (
    MessageState,
    QueueFullError,
    QueueInterface,
    QueueInterfacePopResult,
    QueueMessageMetadata,
    QueueMetrics,
)


@dataclass
class InMemoryMessage:
    """Internal message state tracking."""

    data: bytes
    metadata: QueueMessageMetadata
    visible_after: Optional[float] = None  # None means immediately visible
    processing_start: Optional[float] = None  # When message processing started


class InMemoryQueue(QueueInterface):
    def __init__(
        self,
        max_message_size: Optional[int] = None,
        max_queue_size: Optional[int] = None,
        message_ttl: Optional[int] = None,
        max_delivery_attempts: int = 3,
        default_visibility_timeout: int = 300,
    ):
        super().__init__(
            max_message_size=max_message_size,
            max_queue_size=max_queue_size,
            message_ttl=message_ttl,
            max_delivery_attempts=max_delivery_attempts,
            default_visibility_timeout=default_visibility_timeout,
        )
        # Main message queues
        self._queues: Dict[str, queue.Queue] = defaultdict(queue.Queue)
        # Messages that have been popped but not yet acked/nacked
        self._unacked_messages: Dict[str, Dict[str, InMemoryMessage]] = defaultdict(dict)
        # Dead letter queues
        self._dlq: Dict[str, Dict[str, InMemoryMessage]] = defaultdict(dict)
        # Lock for thread safety
        self._lock = threading.Lock()
        # Processing time tracking (last 100 messages)
        self._processing_times: Dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=100))
        # Failed message counts
        self._failed_counts: Dict[str, int] = defaultdict(int)

    def push(
        self,
        queue_name: str,
        data: bytes,
        visibility_timeout_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
        message_ttl: Optional[int] = None,
    ) -> None:
        self.validate_message(data, queue_name)

        with self._lock:
            if self.max_queue_size and self._queues[queue_name].qsize() >= self.max_queue_size:
                raise QueueFullError(f"Queue {queue_name} is full")

            now = time.time()
            msg = InMemoryMessage(
                data=data,
                metadata=QueueMessageMetadata(
                    enqueued_at=now,
                    delivery_attempts=0,
                    custom=metadata or {},
                    state=MessageState.QUEUED,
                    expires_at=now + (message_ttl or self.message_ttl) if message_ttl or self.message_ttl else None,
                    max_delivery_attempts=self.max_delivery_attempts
                )
            )
            self._queues[queue_name].put((str(uuid.uuid4()), msg))

    def pop(
        self,
        queue_name: str,
        visibility_timeout_seconds: Optional[int] = None,
        wait_timeout_seconds: Optional[float] = None,
    ) -> QueueInterfacePopResult:
        timeout = visibility_timeout_seconds or self.default_visibility_timeout
        now = time.time()
        end_time = now + wait_timeout_seconds if wait_timeout_seconds is not None else None

        while True:
            with self._lock:
                # First check if any unacked messages have timed out or expired
                self._requeue_timed_out_messages(queue_name, now)
                self._cleanup_expired_messages(queue_name, now)

                # Try to get a message
                try:
                    message_id, msg = self._queues[queue_name].get(block=False)
                except queue.Empty:
                    if end_time is None or now >= end_time:
                        raise queue.Empty("No messages available")
                    time.sleep(0.1)  # Don't busy-wait
                    now = time.time()
                    continue

                # Check if message has expired
                if msg.metadata.expires_at and now >= msg.metadata.expires_at:
                    continue

                # Update message state
                msg.metadata.delivery_attempts += 1
                msg.metadata.state = MessageState.IN_PROGRESS
                msg.visible_after = now + timeout
                msg.processing_start = now
                self._unacked_messages[queue_name][message_id] = msg

                return QueueInterfacePopResult(
                    message_id=message_id,
                    data=msg.data,
                    metadata=msg.metadata
                )

    def ack(self, queue_name: str, message_id: str) -> None:
        with self._lock:
            if message_id not in self._unacked_messages[queue_name]:
                raise KeyError(f"Message {message_id} not found in unacked messages for queue {queue_name}")

            msg = self._unacked_messages[queue_name].pop(message_id)
            msg.metadata.state = MessageState.COMPLETED

            # Track processing time
            if msg.processing_start:
                processing_time = time.time() - msg.processing_start
                self._processing_times[queue_name].append(processing_time)

    def nack(
        self,
        queue_name: str,
        message_id: str,
        requeue: bool = True,
        delay_seconds: Optional[int] = None,
        error: Optional[Exception] = None,
    ) -> None:
        with self._lock:
            if message_id not in self._unacked_messages[queue_name]:
                raise KeyError(f"Message {message_id} not found in unacked messages for queue {queue_name}")

            msg = self._unacked_messages[queue_name].pop(message_id)
            self._failed_counts[queue_name] += 1

            if error:
                msg.metadata.custom['last_error'] = str(error)

            if not requeue or (
                msg.metadata.max_delivery_attempts and
                msg.metadata.delivery_attempts >= msg.metadata.max_delivery_attempts
            ):
                msg.metadata.state = MessageState.DEAD_LETTERED
                self._dlq[queue_name][message_id] = msg
                return

            msg.metadata.state = MessageState.QUEUED
            if delay_seconds:
                msg.visible_after = time.time() + delay_seconds
            self._queues[queue_name].put((message_id, msg))

    def get_dlq_messages(
        self,
        queue_name: str,
        limit: Optional[int] = None
    ) -> List[QueueInterfacePopResult]:
        with self._lock:
            messages = list(self._dlq[queue_name].items())
            if limit:
                messages = messages[:limit]
            return [
                QueueInterfacePopResult(
                    message_id=message_id,
                    data=msg.data,
                    metadata=msg.metadata
                )
                for message_id, msg in messages
            ]

    def retry_dlq_message(self, queue_name: str, message_id: str) -> None:
        with self._lock:
            if message_id not in self._dlq[queue_name]:
                raise KeyError(f"Message {message_id} not found in DLQ for queue {queue_name}")

            msg = self._dlq[queue_name].pop(message_id)
            msg.metadata.state = MessageState.QUEUED
            msg.metadata.delivery_attempts = 0
            self._queues[queue_name].put((message_id, msg))

    def purge_dlq(self, queue_name: str) -> int:
        with self._lock:
            count = len(self._dlq[queue_name])
            self._dlq[queue_name].clear()
            return count

    def get_metrics(self, queue_name: str) -> QueueMetrics:
        with self._lock:
            processing_times = list(self._processing_times[queue_name])
            avg_time = sum(processing_times) / len(processing_times) if processing_times else 0.0

            return QueueMetrics(
                depth=self._queues[queue_name].qsize(),
                in_flight=len(self._unacked_messages[queue_name]),
                dlq_depth=len(self._dlq[queue_name]),
                avg_processing_time=avg_time,
                failed_count=self._failed_counts[queue_name],
                custom={}
            )

    def recover_unacked_messages(self, queue_name: str) -> List[QueueInterfacePopResult]:
        with self._lock:
            recovered = []
            for message_id, msg in self._unacked_messages[queue_name].items():
                recovered.append(QueueInterfacePopResult(
                    message_id=message_id,
                    data=msg.data,
                    metadata=msg.metadata
                ))
                msg.metadata.state = MessageState.QUEUED
                msg.visible_after = None
                self._queues[queue_name].put((message_id, msg))
            self._unacked_messages[queue_name].clear()
            return recovered

    def extend_visibility_timeout(
        self,
        queue_name: str,
        message_id: str,
        additional_seconds: int
    ) -> None:
        with self._lock:
            if message_id not in self._unacked_messages[queue_name]:
                raise KeyError(f"Message {message_id} not found in unacked messages for queue {queue_name}")
            msg = self._unacked_messages[queue_name][message_id]
            if msg.visible_after is not None:
                msg.visible_after += additional_seconds

    def _requeue_timed_out_messages(self, queue_name: str, now: float) -> None:
        """Helper to requeue any messages whose visibility timeout has expired."""
        timed_out = []
        for message_id, msg in self._unacked_messages[queue_name].items():
            if msg.visible_after and now >= msg.visible_after:
                timed_out.append(message_id)
                msg.metadata.state = MessageState.QUEUED
                self._queues[queue_name].put((message_id, msg))

        for message_id in timed_out:
            del self._unacked_messages[queue_name][message_id]

    def _cleanup_expired_messages(self, queue_name: str, now: float) -> None:
        """Helper to remove expired messages."""
        # Clean unacked messages
        expired = []
        for message_id, msg in self._unacked_messages[queue_name].items():
            if msg.metadata.expires_at and now >= msg.metadata.expires_at:
                expired.append(message_id)
                msg.metadata.state = MessageState.DEAD_LETTERED
                self._dlq[queue_name][message_id] = msg

        for message_id in expired:
            del self._unacked_messages[queue_name][message_id]

        # Clean DLQ messages (optional, could keep them forever)
        expired = []
        for message_id, msg in self._dlq[queue_name].items():
            if msg.metadata.expires_at and now >= msg.metadata.expires_at:
                expired.append(message_id)

        for message_id in expired:
            del self._dlq[queue_name][message_id]
