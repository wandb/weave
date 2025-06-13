from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel

from weave.trace_server.interface.evaluations.common import JSONSchema

"""
ScorerClass

A ScorerClass is a class of scorers that conform to the same type signature.

"""


class ScorerClassMutableProperties(BaseModel):
    name: str
    description: Optional[str] = None


class ScorerClassImmutableProperties(BaseModel):
    # What the scorer takes as input (e.g., model output, ground truth, input)
    model_input_schema: JSONSchema
    model_output_schema: JSONSchema
    # What the scorer produces (e.g., a score object with value and explanation)
    example_label_schema: JSONSchema
    score_output_schema: JSONSchema
    # Configuration schema for scorer instances
    config_schema: JSONSchema


class ScorerClassUserDefinedProperties(
    ScorerClassMutableProperties, ScorerClassImmutableProperties
): ...


class ScorerClass(ScorerClassUserDefinedProperties):
    id: str


class CreateScorerClassReq(BaseModel):
    properties: ScorerClassUserDefinedProperties


class CreateScorerClassRes(BaseModel):
    id: str


class GetScorerClassReq(BaseModel):
    id: str


class GetScorerClassRes(BaseModel):
    ScorerClass: ScorerClass


class UpdateScorerClassReq(BaseModel):
    id: str
    updates: ScorerClassMutableProperties


class UpdateScorerClassRes(BaseModel):
    pass


class DeleteScorerClassReq(BaseModel):
    id: str


class DeleteScorerClassRes(BaseModel):
    pass


class TSEIMScorerClassMixin(ABC):
    @abstractmethod
    async def async_create_scorer_class(
        self, req: CreateScorerClassReq
    ) -> CreateScorerClassRes: ...

    @abstractmethod
    async def async_get_scorer_class(
        self, req: GetScorerClassReq
    ) -> GetScorerClassRes: ...

    @abstractmethod
    async def async_update_scorer_class(
        self, req: UpdateScorerClassReq
    ) -> UpdateScorerClassRes: ...

    @abstractmethod
    async def async_delete_scorer_class(
        self, req: DeleteScorerClassReq
    ) -> DeleteScorerClassRes: ...
