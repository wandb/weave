import json
import socket
from typing import Iterator
from confluent_kafka import Consumer as ConfluentKafkaConsumer, Producer as ConfluentKafkaProducer

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.environment import wf_kafka_broker_host, wf_kafka_broker_port


CALL_ENDED_TOPIC = "weave.call_ended"


class KafkaProducer(ConfluentKafkaProducer):

    @classmethod
    def from_env(cls) -> "KafkaProducer":
        conf = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
        }
        return cls(conf)

    def produce_call_end(self, call_end: tsi.EndedCallSchemaForInsert) -> None:
        self.produce(
            topic=CALL_ENDED_TOPIC,
            value=call_end.model_dump_json(),
        )
        self.flush()


class KafkaConsumer(ConfluentKafkaConsumer):

    @classmethod
    def from_env(cls) -> "KafkaConsumer":
        conf = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
            "group.id": "weave-scorer-worker",
            "auto.offset.reset": "earliest",
        }
        consumer = cls(conf)
        return consumer
    

def _make_broker_host() -> str:
    return f"{wf_kafka_broker_host()}:{wf_kafka_broker_port()}"
