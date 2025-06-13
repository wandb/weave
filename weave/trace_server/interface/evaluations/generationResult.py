from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

"""
GenerationResult

A GenerationResult is the result of a ModelInstance on a given InputPayload.

"""


class GenerationResultMutableProperties(BaseModel): ...


class GenerationResultImmutableProperties(BaseModel):
    model_instance_id: str
    input_payload_id: str
    result: Any


class GenerationResultUserDefinedProperties(
    BaseModel, GenerationResultMutableProperties, GenerationResultImmutableProperties
): ...


class GenerationResult(BaseModel, GenerationResultUserDefinedProperties):
    id: str


class CreateGenerationResultReq(BaseModel):
    properties: GenerationResultUserDefinedProperties


class CreateGenerationResultRes(BaseModel):
    id: str


class GetGenerationResultReq(BaseModel):
    id: str


class GetGenerationResultRes(BaseModel):
    GenerationResult: GenerationResult


class UpdateGenerationResultReq(BaseModel):
    id: str
    updates: GenerationResultMutableProperties


class UpdateGenerationResultRes(BaseModel):
    pass


class DeleteGenerationResultReq(BaseModel):
    id: str


class DeleteGenerationResultRes(BaseModel):
    pass


class TSEIMGenerationResultMixin(ABC):
    @abstractmethod
    async def async_create_model_instance(
        self, req: CreateGenerationResultReq
    ) -> CreateGenerationResultRes: ...

    @abstractmethod
    async def async_get_model_instance(
        self, req: GetGenerationResultReq
    ) -> GetGenerationResultRes: ...

    @abstractmethod
    async def async_update_model_instance(
        self, req: UpdateGenerationResultReq
    ) -> UpdateGenerationResultRes: ...

    @abstractmethod
    async def async_delete_model_instance(
        self, req: DeleteGenerationResultReq
    ) -> DeleteGenerationResultRes: ...
