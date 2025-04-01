import socket

from confluent_kafka import Producer as ConfluentKafkaProducer

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.environment import wf_kafka_broker_host, wf_kafka_broker_port


_CALL_ENDED_TOPIC = "weave.call_ended"


class KafkaProducer(ConfluentKafkaProducer):

    @classmethod
    def from_env(cls) -> "KafkaProducer":
        conf = {
            "bootstrap.servers": f"{wf_kafka_broker_host()}:{wf_kafka_broker_port()}",
            "client.id": socket.gethostname(),
        }
        return cls(conf)

    def produce_call_end(self, call_end_req: tsi.CallEndReq) -> None:
        self.produce(
            topic=_CALL_ENDED_TOPIC,
            value=call_end_req.model_dump_json(),
        )
        self.flush()
