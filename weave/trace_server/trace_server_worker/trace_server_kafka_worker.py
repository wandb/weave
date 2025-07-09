from weave.trace_server.kafka import KafkaProducer
from weave.trace_server.trace_server_worker import trace_server_worker as tsw


class KafkaProducerWorker(tsw.WorkerInterface):
    def __init__(self, kafka_producer: KafkaProducer):
        self.kafka_producer = kafka_producer

    def submit_evaluate_model_job(
        self, job: tsw.EvaluateModelJob
    ) -> tsw.EvaluateModelSubmission:
        self.kafka_producer.produce_evaluate_model_job(job)
        return tsw.EvaluateModelSubmission()
