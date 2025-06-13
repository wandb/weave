from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel

from weave.trace_server.interface.evaluations.common import JSONSchema, TypedSignature

"""
ModelClass

A ModelClass is a class of models that conform to the same type signature. In particular,
they accept the same input types and produce the same output type. Furthermore, they all
have the same configuration type.

"""


class ModelClassMutableProperties(BaseModel):
    name: str
    description: Optional[str] = None


class ModelClassImmutableProperties(BaseModel):
    signature: TypedSignature
    config_schema: JSONSchema
    # Implementation id???


class ModelClassUserDefinedProperties(
    ModelClassMutableProperties, ModelClassImmutableProperties
): ...


class ModelClass(ModelClassUserDefinedProperties):
    id: str


class CreateModelClassReq(BaseModel):
    properties: ModelClassUserDefinedProperties


class CreateModelClassRes(BaseModel):
    id: str


class GetModelClassReq(BaseModel):
    id: str


class GetModelClassRes(BaseModel):
    result: ModelClass


class UpdateModelClassReq(BaseModel):
    id: str
    updates: ModelClassMutableProperties


class UpdateModelClassRes(BaseModel):
    pass


class DeleteModelClassReq(BaseModel):
    id: str


class DeleteModelClassRes(BaseModel):
    pass


class TSEIMModelClassMixin(ABC):
    @abstractmethod
    async def async_create_model_class(
        self, req: CreateModelClassReq
    ) -> CreateModelClassRes: ...

    @abstractmethod
    async def async_get_model_class(
        self, req: GetModelClassReq
    ) -> GetModelClassRes: ...

    @abstractmethod
    async def async_update_model_class(
        self, req: UpdateModelClassReq
    ) -> UpdateModelClassRes: ...

    @abstractmethod
    async def async_delete_model_class(
        self, req: DeleteModelClassReq
    ) -> DeleteModelClassRes: ...
