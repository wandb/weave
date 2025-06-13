from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

from weave.trace_server.interface.evaluations.common import JSONSchema

"""
ExampleLabel

An ExampleLabel is a ground truth label for a TaskExample.

"""


class ExampleLabelMutableProperties(BaseModel):
    description: Optional[str] = None


class ExampleLabelImmutableProperties(BaseModel):
    task_example_id: str
    label_key: str
    label_schema: JSONSchema
    label_value: Any  # The actual label/ground truth


class ExampleLabelUserDefinedProperties(
    BaseModel, ExampleLabelMutableProperties, ExampleLabelImmutableProperties
): ...


class ExampleLabel(BaseModel, ExampleLabelUserDefinedProperties):
    id: str


class CreateExampleLabelReq(BaseModel):
    properties: ExampleLabelUserDefinedProperties


class CreateExampleLabelRes(BaseModel):
    id: str


class GetExampleLabelReq(BaseModel):
    id: str


class GetExampleLabelRes(BaseModel):
    ExampleLabel: ExampleLabel


class UpdateExampleLabelReq(BaseModel):
    id: str
    updates: ExampleLabelMutableProperties


class UpdateExampleLabelRes(BaseModel):
    pass


class DeleteExampleLabelReq(BaseModel):
    id: str


class DeleteExampleLabelRes(BaseModel):
    pass


class TSEIMExampleLabelMixin(ABC):
    @abstractmethod
    async def async_create_example_label(
        self, req: CreateExampleLabelReq
    ) -> CreateExampleLabelRes: ...

    @abstractmethod
    async def async_get_example_label(
        self, req: GetExampleLabelReq
    ) -> GetExampleLabelRes: ...

    @abstractmethod
    async def async_update_example_label(
        self, req: UpdateExampleLabelReq
    ) -> UpdateExampleLabelRes: ...

    @abstractmethod
    async def async_delete_example_label(
        self, req: DeleteExampleLabelReq
    ) -> DeleteExampleLabelRes: ...
