from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from weave.trace_server.interface.evaluations.common import JSONSchema

"""
InputPayload

A InputPayload is the output of a ModelInstance on a given input.

"""


class InputPayloadMutableProperties(BaseModel): ...


class InputPayloadImmutableProperties(BaseModel):
    payload_schema: JSONSchema
    payload_value: Any


class InputPayloadUserDefinedProperties(
    InputPayloadMutableProperties, InputPayloadImmutableProperties
): ...


class InputPayload(InputPayloadUserDefinedProperties):
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
    async def async_create_input_payload(
        self, req: CreateInputPayloadReq
    ) -> CreateInputPayloadRes: ...

    @abstractmethod
    async def async_get_input_payload(
        self, req: GetInputPayloadReq
    ) -> GetInputPayloadRes: ...

    @abstractmethod
    async def async_update_input_payload(
        self, req: UpdateInputPayloadReq
    ) -> UpdateInputPayloadRes: ...

    @abstractmethod
    async def async_delete_input_payload(
        self, req: DeleteInputPayloadReq
    ) -> DeleteInputPayloadRes: ...
