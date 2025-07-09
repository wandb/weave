from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Queue
from weave.trace_server.kafka import KafkaProducer
from weave.trace_server.run_as_user_worker.run_as_user_worker import RunAsUser, SerializableWorkerClientConfig, ServiceConfig
from weave.trace_server.trace_server_worker import trace_server_worker as tsw
from multiprocessing import Process, Queue

class KafkaProducerWorker(tsw.WorkerInterface):
    def __init__(self, kafka_producer: KafkaProducer):
        self.kafka_producer = kafka_producer

    def submit_evaluate_model_job(self, job: tsw.EvaluateModelJob) -> tsw.EvaluateModelSubmission:
        self.kafka_producer.produce_evaluate_model_job(job)
        return tsw.EvaluateModelSubmission()