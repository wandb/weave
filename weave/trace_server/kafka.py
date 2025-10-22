import json
import logging
import socket
from typing import Any, Optional

import ddtrace
from confluent_kafka import Consumer as ConfluentKafkaConsumer
from confluent_kafka import Producer as ConfluentKafkaProducer
from ddtrace import tracer

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.environment import (
    kafka_broker_host,
    kafka_broker_port,
    kafka_client_password,
    kafka_client_user,
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
        additional_kafka_config: Optional[dict[str, Any]] = None,
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
            "stats_cb": _producer_stats_callback,
            "statistics.interval.ms": 60000,  # Emit stats every 60 seconds
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
            if root_span := ddtrace.tracer.current_root_span():
                root_span.set_tags({"kafka.producer.buffer_size": buffer_size})

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
            if root_span := ddtrace.tracer.current_root_span():
                root_span.set_tags(
                    {
                        "kafka.producer.buffer_size": buffer_size,
                        "kafka.producer.buffer_percentage": buffer_percentage,
                    }
                )

        self.produce(
            topic=CALL_ENDED_TOPIC,
            value=call_end.model_dump_json(),
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
        cls, group_id: str, additional_kafka_config: Optional[dict[str, Any]] = None
    ) -> "KafkaConsumer":
        if additional_kafka_config is None:
            additional_kafka_config = {}

        config = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "stats_cb": _consumer_stats_callback,
            "statistics.interval.ms": 60000,  # Emit stats every 60 seconds
            **_make_auth_config(),
            **additional_kafka_config,
        }

        return cls(config)


def _make_broker_host() -> str:
    return f"{kafka_broker_host()}:{kafka_broker_port()}"


def _make_auth_config() -> dict[str, Optional[str]]:
    username = kafka_client_user()

    if username is None:
        return {}

    return {
        "sasl.username": username,
        "sasl.password": kafka_client_password(),
        "security.protocol": "SASL_PLAINTEXT",
        "sasl.mechanisms": "PLAIN",
    }


def _producer_stats_callback(stats_json_str: str) -> None:
    """Callback to handle Kafka producer statistics and emit metrics to Datadog.

    Args:
        stats_json_str (str): JSON string containing Kafka producer statistics from librdkafka.

    Examples:
        This callback is automatically invoked by librdkafka every statistics.interval.ms.
        It extracts producer metrics and sends them to Datadog
    """
    try:
        stats = json.loads(stats_json_str)
        statsd = tracer.dogstatsd

        # Producer-level metrics
        client_name = stats.get("name", "unknown")
        tags = [f"client_name:{client_name}"]

        # Emit topic-level metrics
        for topic_name, topic_stats in stats.get("topics", {}).items():
            topic_tags = tags + [f"topic:{topic_name}"]

            # Messages produced - librdkafka tracks cumulative txmsgs per partition
            total_msgs = 0
            for partition_stats in topic_stats.get("partitions", {}).values():
                if isinstance(partition_stats, dict):
                    total_msgs += partition_stats.get("txmsgs", 0)

            if total_msgs > 0:
                statsd.gauge(
                    "bufstream.kafka.produce.record.count",
                    value=total_msgs,
                    tags=topic_tags,
                )

            # Track producer queue size (messages waiting to be sent)
            msg_cnt = topic_stats.get("msgq_cnt", 0)
            if msg_cnt >= 0:
                statsd.gauge(
                    "bufstream.kafka.producer.queue.size",
                    value=msg_cnt,
                    tags=topic_tags,
                )

    except Exception as e:
        logger.warning(f"Failed to process Kafka producer stats: {e}")


def _consumer_stats_callback(stats_json_str: str) -> None:
    """Callback to handle Kafka consumer statistics and emit metrics to Datadog.

    Args:
        stats_json_str (str): JSON string containing Kafka consumer statistics from librdkafka.

    Examples:
        This callback is automatically invoked by librdkafka every statistics.interval.ms.
        It extracts consumer metrics like lag and messages consumed.
    """
    try:
        stats = json.loads(stats_json_str)
        statsd = tracer.dogstatsd

        # Consumer-level metrics
        client_name = stats.get("name", "unknown")
        consumer_group = stats.get("rebalance", {}).get("group_id", "unknown")
        tags = [f"client_name:{client_name}", f"consumer_group:{consumer_group}"]

        # Emit topic-level consumer metrics
        for topic_name, topic_stats in stats.get("topics", {}).items():
            topic_tags = tags + [f"topic:{topic_name}"]

            # Consumer lag per partition
            total_lag = 0
            total_msgs_consumed = 0

            for partition_id, partition_stats in topic_stats.get(
                "partitions", {}
            ).items():
                if isinstance(partition_stats, dict) and partition_id != "-1":
                    partition_tags = topic_tags + [f"partition:{partition_id}"]

                    # Consumer lag (how far behind the consumer is)
                    lag = partition_stats.get("consumer_lag", -1)
                    if lag >= 0:
                        total_lag += lag
                        statsd.gauge(
                            "bufstream.kafka.consumer.lag",
                            value=lag,
                            tags=partition_tags,
                        )

                    # Messages consumed
                    msgs_consumed = partition_stats.get("rxmsgs", 0)
                    total_msgs_consumed += msgs_consumed

            # Emit topic-level aggregated metrics
            if total_lag >= 0:
                statsd.gauge(
                    "bufstream.kafka.consumer.lag.total",
                    value=total_lag,
                    tags=topic_tags,
                )

            if total_msgs_consumed > 0:
                statsd.gauge(
                    "bufstream.kafka.consumer.messages.total",
                    value=total_msgs_consumed,
                    tags=topic_tags,
                )

    except Exception as e:
        logger.warning(f"Failed to process Kafka consumer stats: {e}")
