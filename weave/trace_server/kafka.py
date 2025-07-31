import socket

from confluent_kafka import Consumer as ConfluentKafkaConsumer
from confluent_kafka import Producer as ConfluentKafkaProducer

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.environment import (
    kafka_broker_host,
    kafka_broker_port,
    kafka_client_password,
    kafka_client_username,
)

CALL_ENDED_TOPIC = "weave.call_ended"


class KafkaProducer(ConfluentKafkaProducer):
    @classmethod
    def from_env(cls) -> "KafkaProducer":
        config = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
            "message.timeout.ms": 500,
            **_make_auth_config(),
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
    def from_env(cls, group_id: str) -> "KafkaConsumer":
        conf = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            **_make_auth_config(),
        }
        consumer = cls(conf)
        return consumer


def _make_broker_host() -> str:
    return f"{kafka_broker_host()}:{kafka_broker_port()}"


def _make_auth_config() -> dict[str, str]:
    username = kafka_client_username()

    if username is None:
        return {}

    return {
        "sasl.username": username,
        "sasl.password": kafka_client_password(),
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "PLAIN",
    }
