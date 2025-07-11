from abc import ABC, abstractmethod

from pydantic import BaseModel


class EvaluateModelJob(BaseModel):
    project_id: str
    evaluation_ref: str
    model_ref: str
    wb_user_id: str
    evaluation_call_id: str


class EvaluateModelSubmission(BaseModel):
    pass


class WorkerInterface(ABC):
    @abstractmethod
    def submit_evaluate_model_job(
        self, job: EvaluateModelJob
    ) -> EvaluateModelSubmission:
        pass
