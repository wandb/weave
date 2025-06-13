from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel

from weave.trace_server.interface.evaluations.common import TypedSignature

"""
TaskDefinition

A TaskDefinition is a definition of a modelling task - specifically the input and output types.

"""


class TaskDefinitionMutableProperties(BaseModel):
    name: str
    description: Optional[str] = None


class TaskDefinitionImmutableProperties(BaseModel):
    signature: TypedSignature


class TaskDefinitionUserDefinedProperties(
    TaskDefinitionMutableProperties, TaskDefinitionImmutableProperties
): ...


class TaskDefinition(TaskDefinitionUserDefinedProperties):
    id: str


class CreateTaskDefinitionReq(BaseModel):
    properties: TaskDefinitionUserDefinedProperties


class CreateTaskDefinitionRes(BaseModel):
    id: str


class GetTaskDefinitionReq(BaseModel):
    id: str


class GetTaskDefinitionRes(BaseModel):
    TaskDefinition: TaskDefinition


class UpdateTaskDefinitionReq(BaseModel):
    id: str
    updates: TaskDefinitionMutableProperties


class UpdateTaskDefinitionRes(BaseModel):
    pass


class DeleteTaskDefinitionReq(BaseModel):
    id: str


class DeleteTaskDefinitionRes(BaseModel):
    pass


class TSEIMTaskDefinitionMixin(ABC):
    @abstractmethod
    async def async_create_task_definition(
        self, req: CreateTaskDefinitionReq
    ) -> CreateTaskDefinitionRes: ...

    @abstractmethod
    async def async_get_task_definition(
        self, req: GetTaskDefinitionReq
    ) -> GetTaskDefinitionRes: ...

    @abstractmethod
    async def async_update_task_definition(
        self, req: UpdateTaskDefinitionReq
    ) -> UpdateTaskDefinitionRes: ...

    @abstractmethod
    async def async_delete_task_definition(
        self, req: DeleteTaskDefinitionReq
    ) -> DeleteTaskDefinitionRes: ...
