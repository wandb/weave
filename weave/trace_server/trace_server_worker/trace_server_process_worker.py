from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Queue
from weave.trace_server.run_as_user_worker.run_as_user_worker import RunAsUser, SerializableWorkerClientConfig, ServiceConfig
from weave.trace_server.trace_server_worker import trace_server_worker as tsw
from multiprocessing import Process, Queue

class TestOnlyProcessWorker(tsw.WorkerInterface):
    def __init__(self, service_config: ServiceConfig):
        """
        Should only be used for tests!
        """
        self.job_queue = Queue()
        self.result_queue = Queue()
        self.job_process = Process(target=self.process_jobs)
        self.job_process.start()
        self.service_config = service_config

    def stop(self):
        self.job_queue.put(None)
        self.job_process.join()

    def __del__(self):
        self.stop()

    def process_jobs(self):
        while True:
            job = self.job_queue.get()
            if job is None:
                break
            if isinstance(job, tsw.EvaluateModelJob):
                self.handle_evaluate_model_job(job, self.service_config)
            else:
                raise ValueError(f"Unknown job type: {type(job)}")

    def handle_evaluate_model_job(self, job: tsw.EvaluateModelJob, service_config: ServiceConfig) -> None:
        runner = RunAsUser(SerializableWorkerClientConfig(
            project_id=job.project_id,
            user_id=job.wb_user_id,
            service_config=service_config,
        ))
        runner.run(job.evaluation_ref)

    def submit_evaluate_model_job(self, job: tsw.EvaluateModelJob) -> tsw.EvaluateModelSubmission:
        self.job_queue.put(job)
        return tsw.EvaluateModelSubmission()