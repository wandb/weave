"""
Defines a queue interface used by the trace server and workers to process
data using pipelines. 

Queues can be implemented using different backends, for example, Kafka.

The queue interface is used by the trace server to send data to workers.

The queue interface is also used by workers to send data to other workers.

"""

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, TypeVar

from typing_extensions import TypedDict


class QueueError(Exception):
    """Base class for queue errors."""

    pass


class QueueTimeoutError(QueueError):
    """Raised when a queue operation times out."""

    pass


class QueueFullError(QueueError):
    """Raised when a queue is full."""

    pass


class MessageState(enum.Enum):
    """Possible states of a message."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


@dataclass
class QueueMessageMetadata:
    """Metadata associated with a queue message."""

    # When the message was first enqueued
    enqueued_at: float
    # Number of times this message has been delivered
    delivery_attempts: int
    # Custom metadata as key-value pairs
    custom: Dict[str, str]
    # Current state of the message
    state: MessageState = MessageState.QUEUED
    # Time when the message will expire (if set)
    expires_at: Optional[float] = None
    # Maximum number of delivery attempts before moving to DLQ
    max_delivery_attempts: Optional[int] = None


@dataclass
class QueueMetrics:
    """Metrics for a queue."""

    # Number of messages in the queue
    depth: int
    # Number of messages being processed
    in_flight: int
    # Number of messages in the DLQ
    dlq_depth: int
    # Average processing time of last N messages
    avg_processing_time: float
    # Number of failed messages
    failed_count: int
    # Custom metrics
    custom: Dict[str, float]


class QueueInterfacePopResult(TypedDict):
    message_id: str
    data: bytes
    metadata: QueueMessageMetadata


T = TypeVar('T')


class QueueInterface(ABC):
    def __init__(
        self,
        *,
        max_message_size: Optional[int] = None,
        max_queue_size: Optional[int] = None,
        message_ttl: Optional[int] = None,
        max_delivery_attempts: int = 3,
        default_visibility_timeout: int = 300,
    ):
        """Initialize queue interface with common configuration.
        
        Args:
            max_message_size: Maximum size of a message in bytes
            max_queue_size: Maximum number of messages in a queue
            message_ttl: Time-to-live for messages in seconds
            max_delivery_attempts: Maximum number of delivery attempts before moving to DLQ
            default_visibility_timeout: Default message visibility timeout in seconds
        """
        self.max_message_size = max_message_size
        self.max_queue_size = max_queue_size
        self.message_ttl = message_ttl
        self.max_delivery_attempts = max_delivery_attempts
        self.default_visibility_timeout = default_visibility_timeout

    @abstractmethod
    def push(
        self,
        queue_name: str,
        data: bytes,
        visibility_timeout_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
        message_ttl: Optional[int] = None,
    ) -> None:
        """Push a message to the specified queue.
        
        Args:
            queue_name: Name of the queue to push to
            data: Message data as bytes
            visibility_timeout_seconds: If set, message will automatically return to queue
                                     if not acked within this many seconds
            metadata: Optional custom metadata to attach to the message
            message_ttl: Optional message-specific TTL in seconds
            
        Raises:
            QueueFullError: If the queue is full
            ValueError: If the message is too large
        """
        pass

    @abstractmethod
    def pop(
        self,
        queue_name: str,
        visibility_timeout_seconds: Optional[int] = None,
        wait_timeout_seconds: Optional[float] = None,
    ) -> QueueInterfacePopResult:
        """Pop a message from the specified queue.
        
        Args:
            queue_name: Name of the queue to pop from
            visibility_timeout_seconds: Override default visibility timeout for this message
            wait_timeout_seconds: How long to wait for a message (None means no wait)
            
        Returns:
            Dictionary containing message_id, data and metadata
            
        Raises:
            queue.Empty: If no message is available
            QueueTimeoutError: If wait_timeout_seconds is exceeded
        """
        pass

    @abstractmethod
    def ack(self, queue_name: str, message_id: str) -> None:
        """Acknowledge processing of a message.
        
        Args:
            queue_name: Name of the queue the message was from
            message_id: ID of the message to acknowledge
            
        Raises:
            KeyError: If message_id is not found
        """
        pass

    @abstractmethod
    def nack(
        self,
        queue_name: str,
        message_id: str,
        requeue: bool = True,
        delay_seconds: Optional[int] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Negative acknowledge processing of a message.
        
        Args:
            queue_name: Name of the queue the message was from
            message_id: ID of the message to negative acknowledge
            requeue: Whether to requeue the message (True) or move to DLQ (False)
            delay_seconds: If requeuing, optional delay before message is visible again
            error: Optional error that caused the nack
        """
        pass

    @abstractmethod
    def get_dlq_messages(
        self,
        queue_name: str,
        limit: Optional[int] = None
    ) -> List[QueueInterfacePopResult]:
        """Get messages from the dead letter queue.
        
        Args:
            queue_name: Name of the queue to get DLQ messages from
            limit: Maximum number of messages to return
            
        Returns:
            List of messages from the DLQ
        """
        pass

    @abstractmethod
    def retry_dlq_message(
        self,
        queue_name: str,
        message_id: str,
    ) -> None:
        """Move a message from DLQ back to main queue for retry.
        
        Args:
            queue_name: Name of the queue
            message_id: ID of the message to retry
        """
        pass

    @abstractmethod
    def purge_dlq(self, queue_name: str) -> int:
        """Purge all messages from the DLQ.
        
        Args:
            queue_name: Name of the queue whose DLQ to purge
            
        Returns:
            Number of messages purged
        """
        pass

    @abstractmethod
    def get_metrics(self, queue_name: str) -> QueueMetrics:
        """Get metrics for a queue.
        
        Args:
            queue_name: Name of the queue to get metrics for
            
        Returns:
            Queue metrics
        """
        pass

    @abstractmethod
    def recover_unacked_messages(self, queue_name: str) -> List[QueueInterfacePopResult]:
        """Recover any messages that were popped but not acked/nacked.
        
        Args:
            queue_name: Name of the queue to recover messages from
            
        Returns:
            List of recovered messages
        """
        pass

    @abstractmethod
    def extend_visibility_timeout(
        self,
        queue_name: str,
        message_id: str,
        additional_seconds: int
    ) -> None:
        """Extend the visibility timeout for a message that is still being processed.
        
        Args:
            queue_name: Name of the queue the message is from
            message_id: ID of the message
            additional_seconds: Number of additional seconds to hide the message
        """
        pass

    def validate_message(self, data: bytes, queue_name: str) -> None:
        """Validate a message before pushing.
        
        Args:
            data: Message data
            queue_name: Queue name
            
        Raises:
            ValueError: If validation fails
        """
        if not queue_name or not queue_name.strip():
            raise ValueError("Queue name cannot be empty")
        if not queue_name.isalnum() and not all(c in '-_.' for c in queue_name if not c.isalnum()):
            raise ValueError("Queue name can only contain alphanumeric characters, hyphens, underscores and dots")
        if self.max_message_size and len(data) > self.max_message_size:
            raise ValueError(f"Message size {len(data)} exceeds maximum {self.max_message_size}")

    def batch_push(
        self,
        queue_name: str,
        messages: List[tuple[bytes, Optional[Dict[str, str]]]]
    ) -> None:
        """Push multiple messages in a batch.
        
        Default implementation calls push() for each message.
        Implementations should override this for better performance if supported.
        
        Args:
            queue_name: Name of the queue to push to
            messages: List of (data, metadata) tuples to push
        """
        for data, metadata in messages:
            self.push(queue_name, data, metadata=metadata)

    def batch_ack(self, queue_name: str, message_ids: List[str]) -> None:
        """Acknowledge multiple messages in a batch.
        
        Default implementation calls ack() for each message.
        Implementations should override this for better performance if supported.
        
        Args:
            queue_name: Name of the queue the messages are from
            message_ids: List of message IDs to acknowledge
        """
        for message_id in message_ids:
            self.ack(queue_name, message_id)
