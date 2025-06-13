from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

"""
ModelInstance

A ModelInstance is an instance of a ModelClass. The configuration of the model instance
is expected to conform to the configuration type of the ModelClass.

"""


class ModelInstanceMutableProperties(BaseModel):
    name: str
    description: Optional[str] = None


class ModelInstanceImmutableProperties(BaseModel):
    model_class_id: str
    config: Any


class ModelInstanceUserDefinedProperties(
    BaseModel, ModelInstanceMutableProperties, ModelInstanceImmutableProperties
): ...


class ModelInstance(BaseModel, ModelInstanceUserDefinedProperties):
    id: str


class CreateModelInstanceReq(BaseModel):
    properties: ModelInstanceUserDefinedProperties


class CreateModelInstanceRes(BaseModel):
    id: str


class GetModelInstanceReq(BaseModel):
    id: str


class GetModelInstanceRes(BaseModel):
    result: ModelInstance


class UpdateModelInstanceReq(BaseModel):
    id: str
    updates: ModelInstanceMutableProperties


class UpdateModelInstanceRes(BaseModel):
    pass


class DeleteModelInstanceReq(BaseModel):
    id: str


class DeleteModelInstanceRes(BaseModel):
    pass


class TSEIMModelInstanceMixin(ABC):
    @abstractmethod
    async def async_create_model_instance(
        self, req: CreateModelInstanceReq
    ) -> CreateModelInstanceRes: ...

    @abstractmethod
    async def async_get_model_instance(
        self, req: GetModelInstanceReq
    ) -> GetModelInstanceRes: ...

    @abstractmethod
    async def async_update_model_instance(
        self, req: UpdateModelInstanceReq
    ) -> UpdateModelInstanceRes: ...

    @abstractmethod
    async def async_delete_model_instance(
        self, req: DeleteModelInstanceReq
    ) -> DeleteModelInstanceRes: ...
