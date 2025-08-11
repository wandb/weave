import socket
from typing import Any, Optional

from confluent_kafka import Consumer as ConfluentKafkaConsumer
from confluent_kafka import Producer as ConfluentKafkaProducer

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.environment import (
    kafka_broker_host,
    kafka_broker_port,
    kafka_client_password,
    kafka_client_user,
)

CALL_ENDED_TOPIC = "weave.call_ended"


class KafkaProducer(ConfluentKafkaProducer):
    @classmethod
    def from_env(
        cls, additional_config: Optional[dict[str, Any]] = None
    ) -> "KafkaProducer":
        if additional_config is None:
            additional_config = {}

        config = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
            "message.timeout.ms": 500,
            **_make_auth_config(),
            **additional_config,
        }

        return cls(config)

    def produce_call_end(
        self, call_end: tsi.EndedCallSchemaForInsert, flush_immediately: bool = False
    ) -> None:
        self.produce(
            topic=CALL_ENDED_TOPIC,
            value=call_end.model_dump_json(),
        )

        if flush_immediately:
            self.flush()


class KafkaConsumer(ConfluentKafkaConsumer):
    @classmethod
    def from_env(
        cls, group_id: str, additional_config: Optional[dict[str, Any]] = None
    ) -> "KafkaConsumer":
        if additional_config is None:
            additional_config = {}

        config = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            **_make_auth_config(),
            **additional_config,
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
