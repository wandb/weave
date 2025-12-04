import logging
import socket
from typing import Any

from confluent_kafka import Consumer as ConfluentKafkaConsumer
from confluent_kafka import Producer as ConfluentKafkaProducer

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.datadog import set_root_span_dd_tags
from weave.trace_server.environment import (
    kafka_broker_host,
    kafka_broker_port,
    kafka_client_password,
    kafka_client_user,
    kafka_partition_by_project_id,
    kafka_producer_max_buffer_size,
)

CALL_ENDED_TOPIC = "weave.call_ended"

DEFAULT_MAX_BUFFER_SIZE = 10000

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
        buffer_size = len(self)

        if buffer_size >= self.max_buffer_size:
            logger.error(
                "Kafka producer buffer full, dropping message",
                extra={
                    "buffer_size": buffer_size,
                    "max_buffer_size": self.max_buffer_size,
                    "project_id": call_end.project_id,
                    "call_id": call_end.id,
                },
            )
            set_root_span_dd_tags({"kafka.producer.buffer_size": buffer_size})

            # Drop the message - do not produce
            return

        # Log warning if buffer is at 50% capacity
        if buffer_size >= self.max_buffer_size * 0.5:
            buffer_percentage = (buffer_size / self.max_buffer_size) * 100
            logger.warning(
                "Kafka producer buffer at 50%% capacity or higher",
                extra={
                    "buffer_size": buffer_size,
                    "max_buffer_size": self.max_buffer_size,
                    "buffer_percentage": buffer_percentage,
                },
            )
            set_root_span_dd_tags(
                {
                    "kafka.producer.buffer_size": buffer_size,
                    "kafka.producer.buffer_percentage": buffer_percentage,
                }
            )

        publish_key = None
        if kafka_partition_by_project_id():
            publish_key = call_end.project_id

        self.produce(
            topic=CALL_ENDED_TOPIC,
            value=call_end.model_dump_json(),
            key=publish_key,
        )

        if flush_immediately:
            self.flush()


class KafkaConsumer(ConfluentKafkaConsumer):
    """Kafka consumer for receiving messages from the Kafka broker.

    Args:
        group_id (str): The group ID for the consumer.
        additional_kafka_config (Optional[dict[str, Any]]): Additional Kafka configuration to pass to the consumer.
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
            **_make_auth_config(),
            **additional_kafka_config,
        }

        return cls(config)


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
