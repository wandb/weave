import datetime
from typing import Protocol, Optional

from pydantic import BaseModel, Field

class ObjectBackedThing(BaseModel):
    project_id: str
    _object_id: str
    _object_digest: str
    name: str
    description: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: Optional[datetime.datetime]



class Model(ObjectBackedThing):
    id: str

class Task(ObjectBackedThing):
    id: str

class Scorer(ObjectBackedThing):
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
    ...