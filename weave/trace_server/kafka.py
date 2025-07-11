import socket

from confluent_kafka import Consumer as ConfluentKafkaConsumer
from confluent_kafka import Producer as ConfluentKafkaProducer

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.environment import wf_kafka_broker_host, wf_kafka_broker_port
from weave.trace_server.trace_server_worker import trace_server_worker as tsw

CALL_ENDED_TOPIC = "weave.call_ended"
EVALUATE_MODEL_JOB_TOPIC = "weave.evaluate_model_job"


class KafkaProducer(ConfluentKafkaProducer):
    @classmethod
    def from_env(cls) -> "KafkaProducer":
        conf = {
            "bootstrap.servers": _make_broker_host(),
            "client.id": socket.gethostname(),
            "message.timeout.ms": 500,
        }
        return cls(conf)

    def produce_call_end(
        self, call_end: tsi.EndedCallSchemaForInsert, flush_immediately: bool = False
    ) -> None:
        self.produce(
            topic=CALL_ENDED_TOPIC,
            value=call_end.model_dump_json(),
        )
        if flush_immediately:
            self.flush()

    def produce_evaluate_model_job(self, job: tsw.EvaluateModelJob) -> None:
        self.produce(
            topic=EVALUATE_MODEL_JOB_TOPIC,
            value=job.model_dump_json(),
        )
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
        }
        consumer = cls(conf)
        return consumer


def _make_broker_host() -> str:
    return f"{wf_kafka_broker_host()}:{wf_kafka_broker_port()}"
