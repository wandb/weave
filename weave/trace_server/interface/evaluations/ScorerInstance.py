from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

"""
ScorerInstance

A ScorerInstance is a specific instance of a ScorerClass with fixed configuration.

"""


class ScorerInstanceMutableProperties(BaseModel): ...


class ScorerInstanceImmutableProperties(BaseModel):
    scorer_class_id: str
    config: Any


class ScorerInstanceUserDefinedProperties(
    BaseModel, ScorerInstanceMutableProperties, ScorerInstanceImmutableProperties
): ...


class ScorerInstance(BaseModel, ScorerInstanceUserDefinedProperties):
    id: str


class CreateScorerInstanceReq(BaseModel):
    properties: ScorerInstanceUserDefinedProperties


class CreateScorerInstanceRes(BaseModel):
    id: str


class GetScorerInstanceReq(BaseModel):
    id: str


class GetScorerInstanceRes(BaseModel):
    ScorerInstance: ScorerInstance


class UpdateScorerInstanceReq(BaseModel):
    id: str
    updates: ScorerInstanceMutableProperties


class UpdateScorerInstanceRes(BaseModel):
    pass


class DeleteScorerInstanceReq(BaseModel):
    id: str


class DeleteScorerInstanceRes(BaseModel):
    pass


class TSEIMScorerInstanceMixin(ABC):
    @abstractmethod
    async def async_create_scorer_instance(
        self, req: CreateScorerInstanceReq
    ) -> CreateScorerInstanceRes: ...

    @abstractmethod
    async def async_get_scorer_instance(
        self, req: GetScorerInstanceReq
    ) -> GetScorerInstanceRes: ...

    @abstractmethod
    async def async_update_scorer_instance(
        self, req: UpdateScorerInstanceReq
    ) -> UpdateScorerInstanceRes: ...

    @abstractmethod
    async def async_delete_scorer_instance(
        self, req: DeleteScorerInstanceReq
    ) -> DeleteScorerInstanceRes: ...
