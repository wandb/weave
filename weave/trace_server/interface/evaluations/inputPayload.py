from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

"""
InputPayload

A InputPayload is the output of a ModelInstance on a given input.

"""


class InputPayloadMutableProperties(BaseModel): ...


class InputPayloadImmutableProperties(BaseModel):
    payload: Any


class InputPayloadUserDefinedProperties(
    BaseModel, InputPayloadMutableProperties, InputPayloadImmutableProperties
): ...


class InputPayload(BaseModel, InputPayloadUserDefinedProperties):
    id: str


class CreateInputPayloadReq(BaseModel):
    properties: InputPayloadUserDefinedProperties


class CreateInputPayloadRes(BaseModel):
    id: str


class GetInputPayloadReq(BaseModel):
    id: str


class GetInputPayloadRes(BaseModel):
    InputPayload: InputPayload


class UpdateInputPayloadReq(BaseModel):
    id: str
    updates: InputPayloadMutableProperties


class UpdateInputPayloadRes(BaseModel):
    pass


class DeleteInputPayloadReq(BaseModel):
    id: str


class DeleteInputPayloadRes(BaseModel):
    pass


class TSEIMInputPayloadMixin(ABC):
    @abstractmethod
    async def async_create_model_instance(
        self, req: CreateInputPayloadReq
    ) -> CreateInputPayloadRes: ...

    @abstractmethod
    async def async_get_model_instance(
        self, req: GetInputPayloadReq
    ) -> GetInputPayloadRes: ...

    @abstractmethod
    async def async_update_model_instance(
        self, req: UpdateInputPayloadReq
    ) -> UpdateInputPayloadRes: ...

    @abstractmethod
    async def async_delete_model_instance(
        self, req: DeleteInputPayloadReq
    ) -> DeleteInputPayloadRes: ...
