from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel

from weave.trace_server.interface.evaluations.common import TypedSignature

"""
TaskDescription

A TaskDescription is the output of a ModelInstance on a given input.

"""


class TaskDescriptionMutableProperties(BaseModel):
    name: str
    description: Optional[str] = None


class TaskDescriptionImmutableProperties(BaseModel):
    signature: TypedSignature


class TaskDescriptionUserDefinedProperties(
    BaseModel, TaskDescriptionMutableProperties, TaskDescriptionImmutableProperties
): ...


class TaskDescription(BaseModel, TaskDescriptionUserDefinedProperties):
    id: str


class CreateTaskDescriptionReq(BaseModel):
    properties: TaskDescriptionUserDefinedProperties


class CreateTaskDescriptionRes(BaseModel):
    id: str


class GetTaskDescriptionReq(BaseModel):
    id: str


class GetTaskDescriptionRes(BaseModel):
    TaskDescription: TaskDescription


class UpdateTaskDescriptionReq(BaseModel):
    id: str
    updates: TaskDescriptionMutableProperties


class UpdateTaskDescriptionRes(BaseModel):
    pass


class DeleteTaskDescriptionReq(BaseModel):
    id: str


class DeleteTaskDescriptionRes(BaseModel):
    pass


class TSEIMTaskDescriptionMixin(ABC):
    @abstractmethod
    async def async_create_task_description(
        self, req: CreateTaskDescriptionReq
    ) -> CreateTaskDescriptionRes: ...

    @abstractmethod
    async def async_get_task_description(
        self, req: GetTaskDescriptionReq
    ) -> GetTaskDescriptionRes: ...

    @abstractmethod
    async def async_update_task_description(
        self, req: UpdateTaskDescriptionReq
    ) -> UpdateTaskDescriptionRes: ...

    @abstractmethod
    async def async_delete_task_description(
        self, req: DeleteTaskDescriptionReq
    ) -> DeleteTaskDescriptionRes: ...
