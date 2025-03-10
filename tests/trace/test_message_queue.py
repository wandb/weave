from unittest.mock import patch

import pytest

from weave.trace_server.interface.message_queue_provider.in_memory_message_queue import (
    InMemoryMessageQueueProvider,
)


def test_basic_message_queue():
    """Test basic enqueue, dequeue, and acknowledge operations."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic")

    # Test that messages are encoded to bytes
    message_id = queue.enqueue("test_topic", b"test_message")
    assert isinstance(message_id, str)

    messages = queue.dequeue("test_topic")
    assert len(messages) == 1
    dequeued_id, message = messages[0]
    assert message == b"test_message"
    assert dequeued_id == message_id

    # Test that acknowledging removes the message from the queue
    queue.acknowledge("test_topic", message_id)
    assert queue.dequeue("test_topic") == []

    # Verify we can still enqueue/dequeue after acknowledging
    queue.enqueue("test_topic", b"another_message")
    assert len(queue.dequeue("test_topic")) == 1


def test_negative_acknowledge():
    """Test negative acknowledging messages."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic")

    message_id = queue.enqueue("test_topic", b"test_message")
    messages = queue.dequeue("test_topic")
    dequeued_id, _ = messages[0]

    # Test negative acknowledge with a reason
    queue.negative_acknowledge("test_topic", dequeued_id, "Processing error")

    # Message should be removed from the queue (or moved to a DLQ in a real implementation)
    assert queue.dequeue("test_topic") == []

    # In our implementation, the message is just removed, but we should ensure
    # the method tracks the reason properly
    # This would require adding a test-specific method to examine internal state
    # or modifying the provider to support DLQ inspection


def test_topic_existence():
    """Test topic_exists functionality."""
    queue = InMemoryMessageQueueProvider()

    # Topic shouldn't exist initially
    assert not queue.topic_exists("non_existent_topic")

    # Topic should exist after creation
    queue.create_topic("test_topic")
    assert queue.topic_exists("test_topic")

    # Creating a topic twice should be fine
    queue.create_topic("test_topic")
    assert queue.topic_exists("test_topic")


def test_multiple_topics():
    """Test working with multiple topics."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("topic1")
    queue.create_topic("topic2")

    # Enqueue different messages to different topics
    id1 = queue.enqueue("topic1", b"message1")
    id2 = queue.enqueue("topic2", b"message2")

    # Verify messages are in the correct topics
    messages1 = queue.dequeue("topic1")
    assert len(messages1) == 1
    assert messages1[0][1] == b"message1"

    messages2 = queue.dequeue("topic2")
    assert len(messages2) == 1
    assert messages2[0][1] == b"message2"

    # Operations on one topic shouldn't affect the other
    queue.acknowledge("topic1", id1)
    assert queue.dequeue("topic1") == []

    # topic2 should still have its message
    messages2 = queue.dequeue("topic2")
    assert len(messages2) == 0  # Already dequeued once


def test_dequeue_multiple_messages():
    """Test dequeueing multiple messages at once."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic")

    # Enqueue 5 messages
    ids = [queue.enqueue("test_topic", f"message{i}".encode()) for i in range(5)]

    # Dequeue 3 messages
    messages = queue.dequeue("test_topic", 3)
    assert len(messages) == 3

    # Dequeue remaining 2 messages
    remaining = queue.dequeue("test_topic", 3)
    assert len(remaining) == 2

    # Should be empty now
    assert queue.dequeue("test_topic") == []

    # Acknowledge all messages
    for msg_id, _ in messages + remaining:
        queue.acknowledge("test_topic", msg_id)


def test_max_items_limit():
    """Test that max_items limit is enforced."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic", max_items=3)

    # Enqueue more messages than the limit
    ids = [queue.enqueue("test_topic", f"message{i}".encode()) for i in range(5)]

    # Only the 3 most recent should be available (messages 2, 3, and 4)
    messages = queue.dequeue("test_topic", 5)
    assert len(messages) == 3

    # The messages should be the most recent ones
    message_contents = [msg[1] for msg in messages]
    assert b"message2" in message_contents
    assert b"message3" in message_contents
    assert b"message4" in message_contents
    assert b"message0" not in message_contents
    assert b"message1" not in message_contents


@patch("time.time")
def test_ttl_expiration(mock_time):
    """Test that messages expire based on TTL."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic", ttl_seconds=10)

    # Set initial time
    mock_time.return_value = 1000.0

    # Enqueue some messages
    queue.enqueue("test_topic", b"message1")
    queue.enqueue("test_topic", b"message2")

    # Advance time by 5 seconds and add another message
    mock_time.return_value = 1005.0
    queue.enqueue("test_topic", b"message3")

    # Messages shouldn't be expired yet
    messages = queue.dequeue("test_topic", 3)
    assert len(messages) == 3

    # Re-enqueue them (they've been dequeued but not processed)
    # Advance time past TTL for the first two messages
    mock_time.return_value = 1015.0

    # This should cause the two older messages to expire
    messages = queue.dequeue("test_topic", 3)

    # Only the newest message should remain
    assert len(messages) == 1
    assert messages[0][1] == b"message3"


@patch("time.time")
def test_requeue_pending_messages(mock_time):
    """Test requeueing pending messages that exceed the timeout."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic", acknowledge_timeout_seconds=30)

    # Set initial time
    mock_time.return_value = 1000.0

    # Enqueue and dequeue some messages
    id1 = queue.enqueue("test_topic", b"message1")
    id2 = queue.enqueue("test_topic", b"message2")
    id3 = queue.enqueue("test_topic", b"message3")

    # Dequeue all messages
    queue.dequeue("test_topic", 3)

    # Acknowledge one message
    queue.acknowledge("test_topic", id1)

    # Advance time by 15 seconds (half the timeout)
    mock_time.return_value = 1015.0

    # Requeueing shouldn't do anything yet
    requeued = queue.requeue_pending_messages("test_topic")
    assert requeued == 0

    # Advance time beyond the timeout
    mock_time.return_value = 1035.0

    # Now requeueing should work
    requeued = queue.requeue_pending_messages("test_topic")
    assert requeued == 2  # Two messages should be requeued

    # We should be able to dequeue them again
    messages = queue.dequeue("test_topic", 3)
    assert len(messages) == 2

    # The contents should be correct
    contents = [msg[1] for msg in messages]
    assert b"message2" in contents
    assert b"message3" in contents


def test_cleanup():
    """Test cleanup functionality."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic")

    # Enqueue some messages
    queue.enqueue("test_topic", b"message1")
    queue.enqueue("test_topic", b"message2")

    # Dequeue to create pending messages
    queue.dequeue("test_topic", 2)

    # Cleanup should clear everything
    queue.cleanup()

    # Topic should no longer exist
    assert not queue.topic_exists("test_topic")

    # Trying to enqueue to the cleaned topic should raise an error
    with pytest.raises(ValueError):
        queue.enqueue("test_topic", b"message3")


def test_non_existent_topic():
    """Test operations on non-existent topics."""
    queue = InMemoryMessageQueueProvider()

    # All operations on non-existent topics should raise ValueError
    with pytest.raises(ValueError):
        queue.enqueue("non_existent", b"message")

    with pytest.raises(ValueError):
        queue.dequeue("non_existent")

    with pytest.raises(ValueError):
        queue.acknowledge("non_existent", "some_id")

    with pytest.raises(ValueError):
        queue.negative_acknowledge("non_existent", "some_id")

    with pytest.raises(ValueError):
        queue.requeue_pending_messages("non_existent")


def test_invalid_message_id():
    """Test operations with invalid message IDs."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic")

    # Enqueue a valid message
    valid_id = queue.enqueue("test_topic", b"valid_message")

    # Operations with invalid IDs should raise ValueError
    with pytest.raises(ValueError):
        queue.acknowledge("test_topic", "invalid_id")

    with pytest.raises(ValueError):
        queue.negative_acknowledge("test_topic", "invalid_id")

    # Valid ID should work
    queue.dequeue("test_topic")
    queue.acknowledge("test_topic", valid_id)


def test_custom_timeout_for_requeue():
    """Test specifying a custom timeout for requeue_pending_messages."""
    with patch("time.time") as mock_time:
        queue = InMemoryMessageQueueProvider()
        # Set a long default timeout
        queue.create_topic("test_topic", acknowledge_timeout_seconds=600)

        # Set initial time
        mock_time.return_value = 1000.0

        # Enqueue and dequeue a message
        message_id = queue.enqueue("test_topic", b"test_message")
        queue.dequeue("test_topic")

        # Advance time by 30 seconds
        mock_time.return_value = 1030.0

        # Using the default timeout (600s), nothing should be requeued
        assert queue.requeue_pending_messages("test_topic") == 0

        # Using a custom timeout of 20 seconds, the message should be requeued
        assert queue.requeue_pending_messages("test_topic", timeout_seconds=20) == 1

        # We should be able to dequeue it again
        messages = queue.dequeue("test_topic")
        assert len(messages) == 1
        assert messages[0][1] == b"test_message"


def test_dequeue_empty_topic():
    """Test dequeueing from an empty topic."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("empty_topic")

    # Dequeueing from an empty topic should return an empty list
    assert queue.dequeue("empty_topic") == []

    # Dequeueing multiple from an empty topic should also return an empty list
    assert queue.dequeue("empty_topic", 10) == []


def test_dequeue_skips_already_pending():
    """Test that dequeue skips messages that are already being processed."""
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic")

    # Enqueue some messages
    queue.enqueue("test_topic", b"message1")
    queue.enqueue("test_topic", b"message2")
    queue.enqueue("test_topic", b"message3")

    # Dequeue 2 messages, making them pending
    first_batch = queue.dequeue("test_topic", 2)
    assert len(first_batch) == 2

    # Dequeue again without acknowledging
    second_batch = queue.dequeue("test_topic", 2)
    assert len(second_batch) == 1  # Should only get the third message
    assert second_batch[0][1] == b"message3"
