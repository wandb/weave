import datetime
from typing import Optional, Protocol

from pydantic import BaseModel


# class ObjectBackedThing(BaseModel):
#     project_id: str
#     _object_id: str
#     _object_digest: str
#     name: str
#     description: Optional[str]
#     created_at: datetime.datetime
#     updated_at: datetime.datetime
#     deleted_at: Optional[datetime.datetime]

class ModelClass(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class ModelConfig(BaseModel):
    id: str

class ModelInstance(BaseModel):
    id: str
    model_class_id: str # needs to be immutable after creation
    model_config_id: str # needs to be immutable after creation
    name: str
    description: Optional[str] = None
    



class Task(BaseModel):
    id: str


class Scorer(BaseModel):
    id: str


class CallBackedThing(BaseModel):
    project_id: str
    _call_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: Optional[datetime.datetime]


class Result(CallBackedThing):
    id: str
    input_id: str
    model_id: str


class Input(BaseModel):
    id: str


class Example(BaseModel):
    id: str
    taskId: str
    inputId: str


class Label(BaseModel):
    id: str
    exampleId: str


class Comparison(BaseModel):
    id: str


class Score(BaseModel):
    id: str
    comparisonId: Optional[str] = None
    scorerId: str
    resultId: str
    labelId: str
    inputId: str


class Summary(BaseModel):
    id: str
    modelId: str
    taskId: str


class TraceServerEvaluationInterfaceMixin(Protocol):
    def create_model(self, name, config) -> str:
        pass
