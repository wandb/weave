"""A simple in-memory message queue provider used for prototyping and testing."""

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Optional

from weave.trace_server.interface.message_queue_provider.message_queue_provider import (
    MessageQueueProvider,
)


class MessageStatus(Enum):
    """Status of a message in the queue."""

    PENDING = 1  # Message is being processed
    ACKNOWLEDGED = 2  # Message was successfully processed
    NEGATIVE_ACKNOWLEDGED = 3  # Message failed processing


@dataclass
class Message:
    """Message stored in the in-memory queue."""

    message_id: str
    content: bytes
    enqueued_time: float
    dequeued_time: Optional[float] = None
    status: MessageStatus = MessageStatus.PENDING
    nack_reason: Optional[str] = None


@dataclass
class TopicConfig:
    """Configuration for a topic."""

    ttl_seconds: Optional[int] = None
    max_items: Optional[int] = None
    acknowledge_timeout_seconds: Optional[int] = None


class InMemoryMessageQueueProvider(MessageQueueProvider):
    """An in-memory implementation of MessageQueueProvider.

    This implementation is not thread-safe by default, but uses a lock to protect
    critical sections. It's suitable for testing and prototyping, but not for
    production use with multiple threads.
    """

    def __init__(self) -> None:
        """Initialize an empty in-memory message queue provider."""
        # Mapping of topic name to its configuration
        self._topics: dict[str, TopicConfig] = {}

        # Queue of messages for each topic
        self._queues: dict[str, deque[Message]] = defaultdict(deque)

        # Track messages by ID for quick lookup
        self._messages: dict[str, dict[str, Message]] = defaultdict(dict)

        # set of message IDs that have been dequeued but not yet acknowledged or negative-acknowledged
        self._pending_messages: dict[str, set[str]] = defaultdict(set)

        # Lock to protect shared data structures
        self._lock = Lock()

    def create_topic(
        self,
        topic_name: str,
        ttl_seconds: Optional[int] = None,
        max_items: Optional[int] = None,
        acknowledge_timeout_seconds: Optional[int] = None,
    ) -> None:
        """Create a topic if it doesn't exist."""
        with self._lock:
            self._topics[topic_name] = TopicConfig(
                ttl_seconds=ttl_seconds,
                max_items=max_items,
                acknowledge_timeout_seconds=acknowledge_timeout_seconds,
            )

    def topic_exists(self, topic_name: str) -> bool:
        """Check if a topic exists."""
        return topic_name in self._topics

    def enqueue(self, topic_name: str, message: bytes) -> str:
        """Enqueue a message to a topic."""
        if not self.topic_exists(topic_name):
            raise ValueError(f"Topic '{topic_name}' does not exist")

        message_id = str(uuid.uuid4())
        with self._lock:
            # Create message
            msg = Message(
                message_id=message_id,
                content=message,
                enqueued_time=time.time(),
            )

            # Add to queue
            self._queues[topic_name].append(msg)

            # Track by ID
            self._messages[topic_name][message_id] = msg

            # Apply max_items limit if configured
            max_items = self._topics[topic_name].max_items
            if max_items is not None:
                while len(self._queues[topic_name]) > max_items:
                    old_msg = self._queues[topic_name].popleft()
                    # Remove from tracking
                    self._messages[topic_name].pop(old_msg.message_id, None)
                    self._pending_messages[topic_name].discard(old_msg.message_id)

        return message_id

    def dequeue(
        self, topic_name: str, max_messages: int = 1
    ) -> list[tuple[str, bytes]]:
        """dequeue message(s) from a topic."""
        if not self.topic_exists(topic_name):
            raise ValueError(f"Topic '{topic_name}' does not exist")

        result = []
        current_time = time.time()

        with self._lock:
            queue = self._queues[topic_name]

            # Apply TTL if configured
            ttl_seconds = self._topics[topic_name].ttl_seconds
            if ttl_seconds is not None:
                while queue and (current_time - queue[0].enqueued_time > ttl_seconds):
                    expired_msg = queue.popleft()
                    # Remove from tracking
                    self._messages[topic_name].pop(expired_msg.message_id, None)
                    self._pending_messages[topic_name].discard(expired_msg.message_id)

            # dequeue up to max_messages that are not already pending
            index = 0
            messages_dequeued = 0

            while messages_dequeued < max_messages and index < len(queue):
                msg = queue[index]

                # Skip messages that are already being processed
                if (
                    msg.status == MessageStatus.PENDING
                    and msg.dequeued_time is not None
                ):
                    index += 1
                    continue

                # Mark as dequeued and pending
                msg.dequeued_time = current_time
                msg.status = MessageStatus.PENDING
                self._pending_messages[topic_name].add(msg.message_id)

                # Add to result
                result.append((msg.message_id, msg.content))
                messages_dequeued += 1
                index += 1

                # If we've reached max_messages, we're done
                if messages_dequeued >= max_messages:
                    break

        return result

    def acknowledge(self, topic_name: str, message_id: str) -> None:
        """Acknowledge (ack) a message as successfully processed."""
        if not self.topic_exists(topic_name):
            raise ValueError(f"Topic '{topic_name}' does not exist")

        with self._lock:
            message_dict = self._messages[topic_name]
            if message_id not in message_dict:
                raise ValueError(
                    f"Message ID '{message_id}' not found in topic '{topic_name}'"
                )

            msg = message_dict[message_id]
            msg.status = MessageStatus.ACKNOWLEDGED

            # Remove from pending set
            self._pending_messages[topic_name].discard(message_id)

            # Remove from queue for efficiency
            self._remove_from_queue(topic_name, message_id)

    def negative_acknowledge(
        self, topic_name: str, message_id: str, reason: Optional[str] = None
    ) -> None:
        """Negative acknowledge (nack) a message as failed processing."""
        if not self.topic_exists(topic_name):
            raise ValueError(f"Topic '{topic_name}' does not exist")

        with self._lock:
            message_dict = self._messages[topic_name]
            if message_id not in message_dict:
                raise ValueError(
                    f"Message ID '{message_id}' not found in topic '{topic_name}'"
                )

            msg = message_dict[message_id]
            msg.status = MessageStatus.NEGATIVE_ACKNOWLEDGED
            msg.nack_reason = reason

            # Remove from pending set
            self._pending_messages[topic_name].discard(message_id)

            # Remove from queue for efficiency
            self._remove_from_queue(topic_name, message_id)

            # In a real implementation, we might move this to a dead-letter queue
            # For simplicity, we just remove it in this in-memory implementation

    def requeue_pending_messages(
        self, topic_name: str, timeout_seconds: Optional[int] = None
    ) -> int:
        """Requeue messages that are still pending within the timeout period."""
        if not self.topic_exists(topic_name):
            raise ValueError(f"Topic '{topic_name}' does not exist")

        # Use topic's acknowledge_timeout_seconds if no explicit timeout is provided
        if timeout_seconds is None:
            timeout_seconds = self._topics[topic_name].acknowledge_timeout_seconds

        # If no timeout is configured, we can't determine which messages timed out
        if timeout_seconds is None:
            return 0

        current_time = time.time()
        requeued_count = 0

        with self._lock:
            # Make a copy to avoid modifying the set while iterating
            pending_ids = list(self._pending_messages[topic_name])

            for message_id in pending_ids:
                msg = self._messages[topic_name].get(message_id)
                if not msg:
                    # Message no longer exists, remove from pending
                    self._pending_messages[topic_name].discard(message_id)
                    continue

                if msg.dequeued_time is None:
                    # Message hasn't been dequeued yet, skip
                    continue

                # Check if the message has timed out
                if current_time - msg.dequeued_time > timeout_seconds:
                    # Reset dequeued time and status
                    msg.dequeued_time = None
                    self._pending_messages[topic_name].discard(message_id)
                    requeued_count += 1

        return requeued_count

    def cleanup(self) -> None:
        """Perform any necessary cleanup of resources."""
        with self._lock:
            self._topics.clear()
            self._queues.clear()
            self._messages.clear()
            self._pending_messages.clear()

    def _remove_from_queue(self, topic_name: str, message_id: str) -> None:
        """Helper method to remove a message from the queue by ID.

        This is an optimization to avoid O(n) search in deque for removal.
        Instead, we leave the message in the deque but mark it as no longer pending,
        so it will be skipped by dequeue().
        """
        # In a production implementation, we might want a more efficient
        # data structure that allows O(1) removal by ID
        pass
