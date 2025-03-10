from weave.trace_server.interface.message_queue_provider.in_memory_message_queue import (
    InMemoryMessageQueueProvider,
)


def test_basic_message_queue():
    queue = InMemoryMessageQueueProvider()
    queue.create_topic("test_topic")
    queue.enqueue("test_topic", "test_message")
    messages = queue.dequeue("test_topic")
    assert len(messages) == 1
    message_id, message = messages[0]
    assert message == "test_message"
    queue.acknowledge("test_topic", message_id)
    assert queue.dequeue("test_topic") == []
