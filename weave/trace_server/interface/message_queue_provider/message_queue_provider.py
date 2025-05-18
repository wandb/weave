"""
Defines an abstract class supporting Kafka-like queueing of messages.

The underlying implementation can be anything: in-memory, Kafka, Bufstream, etc.

Requirements:

* Create a topic if it doesn't exist.
* Enqueue a message to a topic.
* Dequeue a message from a topic.
* Acknowledge messages (ack) for successful processing.
* Negative acknowledge messages (nack) for failed processing.
* Requeue pending messages that haven't been acked or nacked.

"""

from abc import ABC, abstractmethod
from typing import Optional


class MessageQueueProvider(ABC):
    """Abstract base class for queue providers.

    This interface defines the methods that any queue provider implementation
    must support to be used with the trace server.
    """

    @abstractmethod
    def create_topic(
        self,
        topic_name: str,
        ttl_seconds: Optional[int] = None,
        max_items: Optional[int] = None,
        acknowledge_timeout_seconds: Optional[int] = None,
    ) -> None:
        """Create a topic if it doesn't exist.

        Args:
            topic_name: The name of the topic to create
            ttl_seconds: Optional time-to-live in seconds for the topic
            max_items: Optional maximum number of items in the topic
            acknowledge_timeout_seconds: Optional timeout in seconds for acknowledging messages
        """
        pass

    @abstractmethod
    def topic_exists(self, topic_name: str) -> bool:
        """Check if a topic exists.

        Args:
            topic_name: The name of the topic to check

        Returns:
            True if the topic exists, False otherwise
        """
        pass

    @abstractmethod
    def enqueue(self, topic_name: str, message: bytes) -> str:
        """Enqueue a message to a topic.

        Args:
            topic_name: The name of the topic
            message: The message to enqueue as bytes

        Returns:
            A unique message ID that can be used to acknowledge or negative-acknowledge the message
        """
        pass

    @abstractmethod
    def dequeue(
        self, topic_name: str, max_messages: int = 1
    ) -> list[tuple[str, bytes]]:
        """Dequeue message(s) from a topic.

        Args:
            topic_name: The name of the topic
            max_messages: Maximum number of messages to dequeue

        Returns:
            A list of (message_id, message) tuples, where message is bytes
        """
        pass

    @abstractmethod
    def acknowledge(self, topic_name: str, message_id: str) -> None:
        """Acknowledge (ack) a message as successfully processed.

        Args:
            topic_name: The name of the topic
            message_id: The ID of the message to acknowledge
        """
        pass

    @abstractmethod
    def negative_acknowledge(
        self, topic_name: str, message_id: str, reason: Optional[str] = None
    ) -> None:
        """Negative acknowledge (nack) a message as failed processing.

        This allows for "dead-lettering" of messages that cannot be processed.
        The implementation may choose to move these messages to a dead-letter queue,
        retry them a limited number of times, or handle them in another way.

        Args:
            topic_name: The name of the topic
            message_id: The ID of the message to negative acknowledge
            reason: Optional reason for the failure
        """
        pass

    @abstractmethod
    def requeue_pending_messages(
        self, topic_name: str, timeout_seconds: Optional[int] = None
    ) -> int:
        """Requeue messages that are still pending (neither acked nor nacked) within the timeout period.

        This is important for ensuring message delivery in case a consumer crashes or fails
        to process a message.

        Args:
            topic_name: The name of the topic
            timeout_seconds: Optional timeout in seconds. If provided, only requeue
                             messages that have been pending for longer than this timeout.
                             If None, use the topic's acknowledge_timeout_seconds.

        Returns:
            The number of messages that were requeued
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Perform any necessary cleanup of resources.

        This method should be called when shutting down the application to ensure
        proper resource cleanup and to avoid resource leaks.
        """
        pass
