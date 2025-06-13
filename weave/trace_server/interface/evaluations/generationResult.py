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
    GenerationResultMutableProperties, GenerationResultImmutableProperties
): ...


class GenerationResult(GenerationResultUserDefinedProperties):
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
    async def async_create_generation_result(
        self, req: CreateGenerationResultReq
    ) -> CreateGenerationResultRes: ...

    @abstractmethod
    async def async_get_generation_result(
        self, req: GetGenerationResultReq
    ) -> GetGenerationResultRes: ...

    @abstractmethod
    async def async_update_generation_result(
        self, req: UpdateGenerationResultReq
    ) -> UpdateGenerationResultRes: ...

    @abstractmethod
    async def async_delete_generation_result(
        self, req: DeleteGenerationResultReq
    ) -> DeleteGenerationResultRes: ...
