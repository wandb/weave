from multiprocessing import Process, Queue
from typing import Union

from weave.trace_server.run_as_user_worker.run_as_user_worker import (
    RunAsUser,
    SerializableWorkerClientConfig,
    ServiceConfig,
)
from weave.trace_server.run_as_user_worker.user_scripts.evaluate_model import (
    evaluate_model,
)
from weave.trace_server.trace_server_worker import trace_server_worker as tsw

JobType = Union[tsw.EvaluateModelJob, None]


class TestOnlyProcessWorker(tsw.WorkerInterface):
    def __init__(self, service_config: ServiceConfig):
        """Should only be used for tests!"""
        self.job_queue: Queue[JobType] = Queue()
        self.job_process = Process(target=self.process_jobs)
        self.job_process.start()
        self.service_config = service_config

    def stop(self) -> None:
        self.job_queue.put(None)
        self.job_process.join()

    def __del__(self) -> None:
        self.stop()

    def process_jobs(self) -> None:
        while True:
            job = self.job_queue.get()
            if job is None:
                break
            if isinstance(job, tsw.EvaluateModelJob):
                self.handle_evaluate_model_job(job, self.service_config)
            else:
                raise TypeError(f"Unknown job type: {type(job)}")

    def handle_evaluate_model_job(
        self, job: tsw.EvaluateModelJob, service_config: ServiceConfig
    ) -> None:
        runner = RunAsUser(
            SerializableWorkerClientConfig(
                external_project_id=job.project_id,
                internal_project_id="BROKEN_IDK",
                user_id=job.wb_user_id,
                service_config=service_config,
            )
        )
        runner.execute_internal(
            evaluate_model,
            job,
        )
        runner.stop()

    def submit_evaluate_model_job(
        self, job: tsw.EvaluateModelJob
    ) -> tsw.EvaluateModelSubmission:
        self.job_queue.put(job)
        return tsw.EvaluateModelSubmission()
