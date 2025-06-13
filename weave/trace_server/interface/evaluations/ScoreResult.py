from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

"""
ScoreResult

A ScoreResult is the result of running a ScorerInstance on evaluation data.

"""


class ScoreResultMutableProperties(BaseModel): ...


class ScoreResultImmutableProperties(BaseModel):
    scorer_instance_id: str
    generation_result_id: str
    example_label_id: str
    input_payload_id: str
    comparison_id: Optional[str] = None  # For comparative scoring
    score: Any  # The actual score output
    reason: Optional[str] = None


class ScoreResultUserDefinedProperties(
    ScoreResultMutableProperties, ScoreResultImmutableProperties
): ...


class ScoreResult(ScoreResultUserDefinedProperties):
    id: str


class CreateScoreResultReq(BaseModel):
    properties: ScoreResultUserDefinedProperties


class CreateScoreResultRes(BaseModel):
    id: str


class GetScoreResultReq(BaseModel):
    id: str


class GetScoreResultRes(BaseModel):
    ScoreResult: ScoreResult


class UpdateScoreResultReq(BaseModel):
    id: str
    updates: ScoreResultMutableProperties


class UpdateScoreResultRes(BaseModel):
    pass


class DeleteScoreResultReq(BaseModel):
    id: str


class DeleteScoreResultRes(BaseModel):
    pass


class TSEIMScoreResultMixin(ABC):
    @abstractmethod
    async def async_create_score_result(
        self, req: CreateScoreResultReq
    ) -> CreateScoreResultRes: ...

    @abstractmethod
    async def async_get_score_result(
        self, req: GetScoreResultReq
    ) -> GetScoreResultRes: ...

    @abstractmethod
    async def async_update_score_result(
        self, req: UpdateScoreResultReq
    ) -> UpdateScoreResultRes: ...

    @abstractmethod
    async def async_delete_score_result(
        self, req: DeleteScoreResultReq
    ) -> DeleteScoreResultRes: ...
