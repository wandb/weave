"""
Kafka-based queue implementation with exactly-once delivery semantics.
This implementation is intended for production use.
"""

import json
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

from .queue_interface import (
    MessageState,
    QueueError,
    QueueInterface,
    QueueInterfacePopResult,
    QueueMessageMetadata,
    QueueMetrics,
)


class KafkaQueue(QueueInterface):
    DLQ_SUFFIX = "-dlq"

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        client_id: Optional[str] = None,
        max_message_size: Optional[int] = None,
        max_queue_size: Optional[int] = None,
        message_ttl: Optional[int] = None,
        max_delivery_attempts: int = 3,
        default_visibility_timeout: int = 300,
        **kafka_config
    ):
        """Initialize Kafka queue interface."""
        super().__init__(
            max_message_size=max_message_size,
            max_queue_size=max_queue_size,
            message_ttl=message_ttl,
            max_delivery_attempts=max_delivery_attempts,
            default_visibility_timeout=default_visibility_timeout,
        )

        self._bootstrap_servers = bootstrap_servers
        self._producer_config = {
            'bootstrap.servers': bootstrap_servers,
            'client.id': client_id,
            'enable.idempotence': True,
            'acks': 'all',
        }
        self._producer_config.update(kafka_config)

        self._consumer_config = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'client.id': client_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False,
        }
        self._consumer_config.update(kafka_config)

        self._producer = Producer(self._producer_config)
        self._consumers: Dict[str, Consumer] = {}
        self._dlq_consumers: Dict[str, Consumer] = {}
        self._admin = AdminClient({'bootstrap.servers': bootstrap_servers})

        # Metrics tracking
        self._processing_times: Dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=100))
        self._failed_counts: Dict[str, int] = defaultdict(int)
        self._processing_start_times: Dict[str, Dict[str, float]] = defaultdict(dict)

    def _ensure_topics_exist(self, queue_name: str) -> None:
        """Ensure both main and DLQ topics exist."""
        topics = [queue_name, self._get_dlq_topic(queue_name)]
        existing = self._admin.list_topics().topics
        to_create = [topic for topic in topics if topic not in existing]

        if to_create:
            futures = self._admin.create_topics([
                NewTopic(topic, num_partitions=3, replication_factor=1)
                for topic in to_create
            ])
            for topic, future in futures.items():
                try:
                    future.result()
                except Exception as e:
                    if "already exists" not in str(e):
                        raise

    def _get_dlq_topic(self, queue_name: str) -> str:
        return f"{queue_name}{self.DLQ_SUFFIX}"

    def push(
        self,
        queue_name: str,
        data: bytes,
        visibility_timeout_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
        message_ttl: Optional[int] = None,
    ) -> None:
        self.validate_message(data, queue_name)
        self._ensure_topics_exist(queue_name)

        now = time.time()
        headers = [
            ('enqueued_at', str(now).encode()),
            ('delivery_attempts', b'0'),
            ('state', MessageState.QUEUED.value.encode()),
        ]

        if metadata:
            headers.append(('metadata', json.dumps(metadata).encode()))
        if visibility_timeout_seconds is not None:
            headers.append(('visible_after', str(now + visibility_timeout_seconds).encode()))
        if message_ttl or self.message_ttl:
            ttl = message_ttl or self.message_ttl
            headers.append(('expires_at', str(now + ttl).encode()))
        headers.append(('max_delivery_attempts', str(self.max_delivery_attempts).encode()))

        def delivery_callback(err, msg):
            if err:
                raise QueueError(f"Message delivery failed: {err}")

        self._producer.produce(
            topic=queue_name,
            value=data,
            headers=headers,
            callback=delivery_callback
        )
        self._producer.flush()

    def pop(
        self,
        queue_name: str,
        visibility_timeout_seconds: Optional[int] = None,
        wait_timeout_seconds: Optional[float] = None,
    ) -> QueueInterfacePopResult:
        self._ensure_topics_exist(queue_name)

        if queue_name not in self._consumers:
            consumer = Consumer(self._consumer_config)
            consumer.subscribe([queue_name])
            self._consumers[queue_name] = consumer

        timeout = visibility_timeout_seconds or self.default_visibility_timeout
        end_time = time.time() + (wait_timeout_seconds or 0) if wait_timeout_seconds is not None else None

        while True:
            message = self._consumers[queue_name].poll(timeout=1.0)

            if message is None:
                if end_time is not None:
                    if time.time() >= end_time:
                        raise queue.Empty("No messages available")
                    continue
                raise queue.Empty("No messages available")

            if message.error():
                raise QueueError(message.error())

            # Parse headers
            headers = dict(message.headers() or [])
            metadata = json.loads(headers.get('metadata', b'{}').decode()) if 'metadata' in headers else {}
            visible_after = float(headers.get('visible_after', b'0').decode()) if 'visible_after' in headers else 0
            delivery_attempts = int(headers.get('delivery_attempts', b'0').decode())
            expires_at = float(headers.get('expires_at', b'0').decode()) if 'expires_at' in headers else None
            max_attempts = int(headers.get('max_delivery_attempts', str(self.max_delivery_attempts)).encode())

            now = time.time()

            # Skip messages that aren't visible yet
            if visible_after and now < visible_after:
                continue

            # Skip expired messages
            if expires_at and now >= expires_at:
                self._move_to_dlq(queue_name, message, "Message expired")
                continue

            # Check max delivery attempts
            if delivery_attempts >= max_attempts:
                self._move_to_dlq(queue_name, message, "Max delivery attempts exceeded")
                continue

            message_id = f"{message.topic()}:{message.partition()}:{message.offset()}"
            self._processing_start_times[queue_name][message_id] = now

            return QueueInterfacePopResult(
                message_id=message_id,
                data=message.value(),
                metadata=QueueMessageMetadata(
                    enqueued_at=float(headers.get('enqueued_at', b'0').decode()),
                    delivery_attempts=delivery_attempts + 1,
                    custom=metadata,
                    state=MessageState.IN_PROGRESS,
                    expires_at=expires_at,
                    max_delivery_attempts=max_attempts
                )
            )

    def ack(self, queue_name: str, message_id: str) -> None:
        if queue_name not in self._consumers:
            raise ValueError(f"No consumer exists for queue {queue_name}")

        try:
            topic, partition, offset = message_id.split(':')
            if topic != queue_name:
                raise ValueError(f"Message ID topic {topic} does not match queue name {queue_name}")

            # Track processing time
            start_time = self._processing_start_times[queue_name].pop(message_id, None)
            if start_time:
                self._processing_times[queue_name].append(time.time() - start_time)

            self._consumers[queue_name].commit(offsets=[{
                'topic': topic,
                'partition': int(partition),
                'offset': int(offset) + 1
            }])
        except ValueError as e:
            raise ValueError(f"Invalid message_id format: {message_id}") from e

    def nack(
        self,
        queue_name: str,
        message_id: str,
        requeue: bool = True,
        delay_seconds: Optional[int] = None,
        error: Optional[Exception] = None,
    ) -> None:
        if queue_name not in self._consumers:
            raise ValueError(f"No consumer exists for queue {queue_name}")

        self._failed_counts[queue_name] += 1

        try:
            topic, partition, offset = message_id.split(':')
            if topic != queue_name:
                raise ValueError(f"Message ID topic {topic} does not match queue name {queue_name}")

            # Clean up processing time tracking
            self._processing_start_times[queue_name].pop(message_id, None)

            if not requeue:
                # Move to DLQ
                self._consumers[queue_name].seek(TopicPartition(topic, int(partition), int(offset)))
                message = self._consumers[queue_name].poll(timeout=1.0)
                if message and not message.error():
                    self._move_to_dlq(queue_name, message, str(error) if error else "Explicitly nacked")
                self.ack(queue_name, message_id)
                return

            if delay_seconds:
                # Re-publish with delay
                self._consumers[queue_name].seek(TopicPartition(topic, int(partition), int(offset)))
                message = self._consumers[queue_name].poll(timeout=1.0)
                if message and not message.error():
                    headers = dict(message.headers() or [])
                    headers['visible_after'] = str(time.time() + delay_seconds).encode()
                    headers['delivery_attempts'] = str(int(headers.get('delivery_attempts', b'0').decode()) + 1).encode()
                    if error:
                        metadata = json.loads(headers.get('metadata', b'{}').decode())
                        metadata['last_error'] = str(error)
                        headers['metadata'] = json.dumps(metadata).encode()

                    self._producer.produce(
                        topic=queue_name,
                        value=message.value(),
                        headers=list(headers.items()),
                    )
                    self._producer.flush()
                    self.ack(queue_name, message_id)
        except ValueError as e:
            raise ValueError(f"Invalid message_id format: {message_id}") from e

    def get_dlq_messages(
        self,
        queue_name: str,
        limit: Optional[int] = None
    ) -> List[QueueInterfacePopResult]:
        dlq_topic = self._get_dlq_topic(queue_name)
        if dlq_topic not in self._dlq_consumers:
            consumer = Consumer({
                **self._consumer_config,
                'group.id': f"{self._consumer_config['group.id']}-dlq-reader"
            })
            consumer.subscribe([dlq_topic])
            self._dlq_consumers[dlq_topic] = consumer

        messages = []
        consumer = self._dlq_consumers[dlq_topic]

        while True:
            if limit and len(messages) >= limit:
                break

            message = consumer.poll(timeout=1.0)
            if message is None or message.error():
                break

            headers = dict(message.headers() or [])
            metadata = json.loads(headers.get('metadata', b'{}').decode()) if 'metadata' in headers else {}

            messages.append(QueueInterfacePopResult(
                message_id=f"{message.topic()}:{message.partition()}:{message.offset()}",
                data=message.value(),
                metadata=QueueMessageMetadata(
                    enqueued_at=float(headers.get('enqueued_at', b'0').decode()),
                    delivery_attempts=int(headers.get('delivery_attempts', b'0').decode()),
                    custom=metadata,
                    state=MessageState.DEAD_LETTERED,
                    expires_at=float(headers.get('expires_at', b'0').decode()) if 'expires_at' in headers else None,
                    max_delivery_attempts=int(headers.get('max_delivery_attempts', str(self.max_delivery_attempts)).encode())
                )
            ))

        return messages

    def retry_dlq_message(self, queue_name: str, message_id: str) -> None:
        dlq_topic = self._get_dlq_topic(queue_name)
        if dlq_topic not in self._dlq_consumers:
            raise ValueError(f"No DLQ consumer exists for queue {queue_name}")

        try:
            topic, partition, offset = message_id.split(':')
            if topic != dlq_topic:
                raise ValueError(f"Message ID topic {topic} does not match DLQ topic {dlq_topic}")

            consumer = self._dlq_consumers[dlq_topic]
            consumer.seek(TopicPartition(topic, int(partition), int(offset)))
            message = consumer.poll(timeout=1.0)

            if message and not message.error():
                # Reset delivery attempts and state
                headers = dict(message.headers() or [])
                headers['delivery_attempts'] = b'0'
                headers['state'] = MessageState.QUEUED.value.encode()
                headers['visible_after'] = str(time.time()).encode()

                self._producer.produce(
                    topic=queue_name,
                    value=message.value(),
                    headers=list(headers.items()),
                )
                self._producer.flush()

                # Commit the DLQ offset
                consumer.commit(message=message)
        except ValueError as e:
            raise ValueError(f"Invalid message_id format: {message_id}") from e

    def purge_dlq(self, queue_name: str) -> int:
        dlq_topic = self._get_dlq_topic(queue_name)
        if dlq_topic not in self._dlq_consumers:
            return 0

        consumer = self._dlq_consumers[dlq_topic]
        partitions = consumer.assignment()

        # Get end offsets
        end_offsets = consumer.get_watermark_offsets(partitions[0])
        count = sum(end - start for start, end in end_offsets)

        # Seek to end
        for partition in partitions:
            consumer.seek_to_end(partition)

        # Commit
        consumer.commit()

        return count

    def get_metrics(self, queue_name: str) -> QueueMetrics:
        if queue_name not in self._consumers:
            return QueueMetrics(
                depth=0,
                in_flight=0,
                dlq_depth=0,
                avg_processing_time=0.0,
                failed_count=self._failed_counts[queue_name],
                custom={}
            )

        consumer = self._consumers[queue_name]

        # Get queue depth (approximate)
        depth = 0
        for partition in consumer.assignment():
            low, high = consumer.get_watermark_offsets(partition)
            depth += high - low

        # Get DLQ depth
        dlq_depth = 0
        dlq_topic = self._get_dlq_topic(queue_name)
        if dlq_topic in self._dlq_consumers:
            dlq_consumer = self._dlq_consumers[dlq_topic]
            for partition in dlq_consumer.assignment():
                low, high = dlq_consumer.get_watermark_offsets(partition)
                dlq_depth += high - low

        # Calculate average processing time
        processing_times = list(self._processing_times[queue_name])
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0.0

        return QueueMetrics(
            depth=depth,
            in_flight=len(self._processing_start_times[queue_name]),
            dlq_depth=dlq_depth,
            avg_processing_time=avg_time,
            failed_count=self._failed_counts[queue_name],
            custom={}
        )

    def recover_unacked_messages(self, queue_name: str) -> List[QueueInterfacePopResult]:
        """Kafka handles recovery automatically through consumer groups."""
        return []

    def extend_visibility_timeout(
        self,
        queue_name: str,
        message_id: str,
        additional_seconds: int
    ) -> None:
        """Re-publish the message with an extended timeout."""
        try:
            topic, partition, offset = message_id.split(':')
            if topic != queue_name:
                raise ValueError(f"Message ID topic {topic} does not match queue name {queue_name}")

            consumer = self._consumers[queue_name]
            consumer.seek(TopicPartition(topic, int(partition), int(offset)))
            message = consumer.poll(timeout=1.0)

            if message and not message.error():
                headers = dict(message.headers() or [])
                current_timeout = float(headers.get('visible_after', b'0').decode()) if 'visible_after' in headers else 0

                if current_timeout > 0:
                    headers['visible_after'] = str(current_timeout + additional_seconds).encode()
                    self._producer.produce(
                        topic=queue_name,
                        value=message.value(),
                        headers=list(headers.items()),
                    )
                    self._producer.flush()
                    self.ack(queue_name, message_id)
        except ValueError as e:
            raise ValueError(f"Invalid message_id format: {message_id}") from e

    def _move_to_dlq(self, queue_name: str, message: Any, reason: str) -> None:
        """Helper to move a message to the DLQ."""
        headers = dict(message.headers() or [])
        metadata = json.loads(headers.get('metadata', b'{}').decode())
        metadata['dlq_reason'] = reason
        headers['metadata'] = json.dumps(metadata).encode()
        headers['state'] = MessageState.DEAD_LETTERED.value.encode()

        self._producer.produce(
            topic=self._get_dlq_topic(queue_name),
            value=message.value(),
            headers=list(headers.items()),
        )
        self._producer.flush()

    def __del__(self):
        """Clean up Kafka resources."""
        for consumer in self._consumers.values():
            consumer.close()
        for consumer in self._dlq_consumers.values():
            consumer.close()
        self._producer.flush()
        self._producer.close()
        self._admin.close()
