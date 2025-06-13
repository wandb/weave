from abc import ABC, abstractmethod

from pydantic import BaseModel

"""
TaskExample

A TaskExample is a specific example of a TaskDefinition for which to evaluate a ModelInstance.

"""


class TaskExampleMutableProperties(BaseModel): ...


class TaskExampleImmutableProperties(BaseModel):
    task_definition_id: str
    input_payload_id: str


class TaskExampleUserDefinedProperties(
 TaskExampleMutableProperties, TaskExampleImmutableProperties
): ...


class TaskExample(TaskExampleUserDefinedProperties):
    id: str


class CreateTaskExampleReq(BaseModel):
    properties: TaskExampleUserDefinedProperties


class CreateTaskExampleRes(BaseModel):
    id: str


class GetTaskExampleReq(BaseModel):
    id: str


class GetTaskExampleRes(BaseModel):
    TaskExample: TaskExample


class UpdateTaskExampleReq(BaseModel):
    id: str
    updates: TaskExampleMutableProperties


class UpdateTaskExampleRes(BaseModel):
    pass


class DeleteTaskExampleReq(BaseModel):
    id: str


class DeleteTaskExampleRes(BaseModel):
    pass


class TSEIMTaskExampleMixin(ABC):
    @abstractmethod
    async def async_create_task_example(
        self, req: CreateTaskExampleReq
    ) -> CreateTaskExampleRes: ...

    @abstractmethod
    async def async_get_task_example(
        self, req: GetTaskExampleReq
    ) -> GetTaskExampleRes: ...

    @abstractmethod
    async def async_update_task_example(
        self, req: UpdateTaskExampleReq
    ) -> UpdateTaskExampleRes: ...

    @abstractmethod
    async def async_delete_task_example(
        self, req: DeleteTaskExampleReq
    ) -> DeleteTaskExampleRes: ...
