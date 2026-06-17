import logging
import socket
import zlib
from typing import Any

from confluent_kafka import (
    Consumer as ConfluentKafkaConsumer,
)
from confluent_kafka import (
    Producer as ConfluentKafkaProducer,
)
from confluent_kafka import (
    TopicPartition,
)

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.kafka_events import (
    SCORE_AGENT_SPANS_TOPIC,
    ScoreAgentSpansEvent,
)
from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.environment import (
    kafka_broker_host,
    kafka_broker_port,
    kafka_client_password,
    kafka_client_user,
    kafka_producer_max_buffer_size,
    wf_kafka_project_id_bucket_count,
)
from weave.trace_server.tracing import traced

CALL_ENDED_TOPIC = "weave.call_ended"
SCORE_CALLS_TOPIC = "weave.score_calls"

DEFAULT_MAX_BUFFER_SIZE = 100000
# Fraction of `max_buffer_size` at which a "buffer pressure" warning is logged.
BUFFER_WARN_THRESHOLD = 0.5

logger = logging.getLogger(__name__)


class KafkaProducer(ConfluentKafkaProducer):
    """Kafka producer for sending messages to the Kafka broker.

    Args:
        config (dict[str, Any]): Kafka producer configuration.
        max_buffer_size (int): Maximum number of messages in the producer buffer.
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.max_buffer_size = (
            kafka_producer_max_buffer_size() or DEFAULT_MAX_BUFFER_SIZE
        )

    @classmethod
    def from_env(
        cls,
        additional_kafka_config: dict[str, Any] | None = None,
    ) -> "KafkaProducer":
        if additional_kafka_config is None:
            additional_kafka_config = {}

        num_retries = 1
        request_retry_backoff_ms = 100
        # per attempt deadline, this is large to accommodate large call batches,
        # with only 1 retry to prevent continued failures when timeout is due to size
        request_timeout_ms = 5000
        # worst case total request time hardcap
        total_timeout_ms = (
            request_timeout_ms * (num_retries + 1) + request_retry_backoff_ms
        )
        config = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
            "request.timeout.ms": request_timeout_ms,
            "message.timeout.ms": total_timeout_ms,
            "retries": 1,
            "retry.backoff.ms": request_retry_backoff_ms,
            "partitioner": "murmur2_random",  # Explicit round robin
            **_make_auth_config(),
            **additional_kafka_config,
        }

        return cls(config)

    def produce_call_end(
        self, call_end: tsi.EndedCallSchemaForInsert, flush_immediately: bool = False
    ) -> None:
        """Produce a call_end message to Kafka with buffer size management.

        Drops messages if buffer is full to prevent unbounded memory growth.
        Logs warnings at 50% capacity and errors when dropping messages.
        """
        if self._check_buffer_pressure(
            message_type="call_end",
            logging_extra={"project_id": call_end.project_id, "call_id": call_end.id},
        ):
            return

        self.produce(
            topic=CALL_ENDED_TOPIC,
            value=call_end.model_dump_json(),
            key=_bucketed_project_key(call_end.project_id, call_end.id),
        )

        if flush_immediately:
            # Use a short non-blocking flush instead of an unbounded flush().
            # The producer is a process-level singleton shared across all request
            # threads, so flush() (no timeout) blocks until ALL in-flight messages
            # from every concurrent request are acknowledged — causing a convoy
            # effect under load.  flush(0) triggers a delivery attempt for queued
            # messages and returns immediately.
            self.flush(0)

    SCORE_CALLS_CHUNK_SIZE = 100

    def produce_score_calls(
        self, req: tsi.CallsScoreReq, flush_immediately: bool = True
    ) -> None:
        """Produce score_calls messages to Kafka, chunked to avoid consumer timeouts.

        Large call_ids lists are split into chunks of SCORE_CALLS_CHUNK_SIZE
        so that each Kafka message can be processed within the consumer's
        max.poll.interval.ms.

        Args:
            req: The CallsScoreReq containing project_id, call_ids, scorer_refs, and wb_user_id
            flush_immediately: Whether to flush the producer immediately (default True)
        """
        if self._check_buffer_pressure(
            message_type="score_calls",
            logging_extra={
                "project_id": req.project_id,
                "call_ids_count": len(req.call_ids),
            },
        ):
            return

        for i in range(0, len(req.call_ids), self.SCORE_CALLS_CHUNK_SIZE):
            chunk = req.call_ids[i : i + self.SCORE_CALLS_CHUNK_SIZE]
            self.produce(
                topic=SCORE_CALLS_TOPIC,
                value=req.model_copy(update={"call_ids": chunk}).model_dump_json(),
                key=_bucketed_project_key(req.project_id, chunk[0]),
            )

        if flush_immediately:
            self.flush(0)

    @traced(name="kafka_producer.produce_score_agent_spans")
    def produce_score_agent_spans(self, event: ScoreAgentSpansEvent) -> None:
        """Produce a weave.score_agent_spans event to Kafka.

        Drops the message when the producer buffer is full (same policy as `produce_call_end`).
        """
        if self._check_buffer_pressure(
            message_type="score_agent_spans",
            logging_extra={
                "event_type": event.event_type,
                "status_code": event.status_code,
                "project_id": event.project_id,
                "trace_id": event.trace_id,
                "span_id": event.span_id,
            },
        ):
            return

        # Partition by conversation_id if available, falling back to trace_id.
        # This ensures spans for the same conversation or turn always route to
        # the same worker, which allows for more efficient caching/querying in
        # the scoring worker. We intentionally do NOT partition on project_id:
        # that would send all spans for a project to a single worker instance.
        publish_key = event.conversation_id or event.trace_id
        self.produce(
            topic=SCORE_AGENT_SPANS_TOPIC,
            value=event.model_dump_json(),
            key=publish_key,
        )

    def _check_buffer_pressure(
        self, message_type: str, logging_extra: dict[str, str | int] | None = None
    ) -> bool:
        """Check producer buffer pressure before a `produce(...)` call.

        Returns True when the buffer is full and the caller MUST drop the
        message; in that case an error is logged with `drop_log_message` and
        `extra` (caller-supplied identifiers like project_id / call_id /
        trace_id) and a DD tag is set.

        At >= BUFFER_WARN_THRESHOLD of capacity a warning is logged but the
        call is allowed to proceed (returns False).
        """
        buffer_size = len(self)

        if buffer_size >= self.max_buffer_size:
            logger.error(
                "Kafka producer buffer full, dropping message %r",
                message_type,
                extra={
                    "buffer_size": buffer_size,
                    "max_buffer_size": self.max_buffer_size,
                    **(logging_extra or {}),
                },
            )
            set_current_span_dd_tags({"kafka.producer.buffer_size": buffer_size})
            return True

        if buffer_size >= self.max_buffer_size * BUFFER_WARN_THRESHOLD:
            buffer_percentage = (buffer_size / self.max_buffer_size) * 100
            logger.warning(
                "Kafka producer buffer at 50%% capacity or higher for message type %r",
                message_type,
                extra={
                    "buffer_size": buffer_size,
                    "max_buffer_size": self.max_buffer_size,
                    "buffer_percentage": buffer_percentage,
                    **(logging_extra or {}),
                },
            )
            set_current_span_dd_tags(
                {
                    "kafka.producer.buffer_size": buffer_size,
                    "kafka.producer.buffer_percentage": buffer_percentage,
                }
            )

        return False


class KafkaConsumer(ConfluentKafkaConsumer):
    """Kafka consumer for receiving messages from the Kafka broker.

    Args:
        group_id (str): The group ID for the consumer.
        additional_kafka_config (dict[str, Any] | None): Additional Kafka configuration to pass to the consumer.
    """

    @classmethod
    def from_env(
        cls, group_id: str, additional_kafka_config: dict[str, Any] | None = None
    ) -> "KafkaConsumer":
        if additional_kafka_config is None:
            additional_kafka_config = {}

        config = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            # Connection health: detect dead sockets in 10s instead of the
            # 60s default.  Without this, a dropped connection blocks heartbeats
            # for up to a minute, which can exceed the session timeout and
            # trigger an unnecessary consumer-group rebalance.
            "socket.timeout.ms": 10_000,
            # Session / heartbeat: keep session.timeout high enough to ride out
            # transient coordinator slowness (commit backlogs, broker GC pauses)
            # without falsely declaring the consumer dead.  The key invariant is
            #   socket.timeout.ms  <  session.timeout.ms
            # so dead-socket detection fires before the session expires.
            "session.timeout.ms": 45_000,
            "heartbeat.interval.ms": 3_000,
            # Reconnection: back off quickly but cap at 5s so we rejoin the
            # group fast after a transient failure.
            "reconnect.backoff.ms": 100,
            "reconnect.backoff.max.ms": 5_000,
            # TODO: Re-enable once prod Bufstream supports Kafka >= 2.4.0 protocol.
            # "partition.assignment.strategy": "cooperative-sticky",  # KIP-429, requires >= 2.4.0
            # "group.instance.id": socket.gethostname(),  # KIP-345, requires >= 2.3.0
            **_make_auth_config(),
            **additional_kafka_config,
        }

        return cls(config)

    def commit_batch_async(self, messages: list[Any]) -> None:
        """Commit the highest offset per partition in a single async call.

        Replaces N synchronous per-message commits with one non-blocking call,
        which keeps the coordinator connection free for heartbeats.

        Args:
            messages: Raw confluent-kafka Message objects to commit.
        """
        if not messages:
            return

        # Keep only the highest offset per (topic, partition).
        max_offsets: dict[tuple[str, int], int] = {}
        for msg in messages:
            key = (msg.topic(), msg.partition())
            offset = msg.offset()
            if key not in max_offsets or offset > max_offsets[key]:
                max_offsets[key] = offset

        # commit position = next offset the consumer should read
        offsets = [
            TopicPartition(topic, partition, offset + 1)
            for (topic, partition), offset in max_offsets.items()
        ]

        try:
            self.commit(offsets=offsets, asynchronous=True)
        except Exception:
            # Async commit failure is non-fatal: the messages will be
            # redelivered on the next rebalance and reprocessed.
            logger.warning("Async batch commit failed", exc_info=True)


def _bucketed_project_key(project_id: str, bucket_seed: str) -> str:
    """Partition key with optional bucket suffix for spreading hot projects."""
    bucket_count = wf_kafka_project_id_bucket_count()
    if bucket_count <= 1:
        return project_id
    # crc32 picks the bucket; the murmur2 partitioner re-hashes the composite key,
    # so bucket_count caps (not equals) the partitions a project spreads across.
    bucket = zlib.crc32(bucket_seed.encode()) % bucket_count
    return f"{project_id}:{bucket}"


def _make_broker_host() -> str:
    return f"{kafka_broker_host()}:{kafka_broker_port()}"


def _make_auth_config() -> dict[str, str | None]:
    username = kafka_client_user()

    if username is None:
        return {}

    return {
        "sasl.username": username,
        "sasl.password": kafka_client_password(),
        "security.protocol": "SASL_PLAINTEXT",
        "sasl.mechanisms": "PLAIN",
    }
