from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from weave.trace_server.intent_vectors import config

ShortString = Annotated[str, Field(min_length=1, max_length=512)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntentInput(StrictModel):
    intent_id: ShortString
    signature: str
    request_type: ShortString
    status: ShortString
    source: ShortString
    source_id: str = Field(default="", max_length=2048)
    role: str = Field(default="", max_length=128)
    event_time: datetime
    attributes: dict[str, str] = Field(default_factory=dict)

    @field_validator("signature")
    @classmethod
    def signature_has_bounded_normalized_length(cls, value: str) -> str:
        normalized = " ".join(value.lower().split())
        if not normalized:
            raise ValueError("signature must not be empty after normalization")
        if len(normalized) > config.MAX_SIGNATURE_CHARS:
            raise ValueError(
                f"normalized signature exceeds {config.MAX_SIGNATURE_CHARS} characters"
            )
        return value


class BatchUpsertRequest(StrictModel):
    intents: list[IntentInput] = Field(min_length=1, max_length=config.MAX_BATCH_SIZE)

    @model_validator(mode="after")
    def intent_ids_are_unique(self) -> BatchUpsertRequest:
        ids = [item.intent_id for item in self.intents]
        if len(ids) != len(set(ids)):
            raise ValueError("intent_id values must be unique within a batch")
        return self


class BatchUpsertResponse(StrictModel):
    upserted: int


class IntentFilters(StrictModel):
    intent_id: str | None = Field(default=None, max_length=512)
    request_type: str | None = Field(default=None, max_length=512)
    status: str | None = Field(default=None, max_length=512)
    source: str | None = Field(default=None, max_length=512)
    event_time_from: datetime | None = None
    event_time_to: datetime | None = None

    @model_validator(mode="after")
    def event_time_range_is_ordered(self) -> IntentFilters:
        if (
            self.event_time_from is not None
            and self.event_time_to is not None
            and self.event_time_from > self.event_time_to
        ):
            raise ValueError("event_time_from must not exceed event_time_to")
        return self


class IntentQueryRequest(StrictModel):
    filters: IntentFilters = Field(default_factory=IntentFilters)
    limit: int = Field(default=100, ge=1, le=config.MAX_LIST_RESULTS)


class IntentRecord(StrictModel):
    intent_id: str
    version: int
    signature: str
    normalized_signature: str
    request_type: str
    status: str
    source: str
    source_id: str
    role: str
    event_time: datetime
    attributes: dict[str, str]
    embedding_model: str
    embedding_dimensions: int
    created_by_user_id: str
    created_at: datetime


class IntentQueryResponse(StrictModel):
    intents: list[IntentRecord]


class IntentSearchRequest(StrictModel):
    query: str
    k: int = Field(default=20, ge=1, le=config.MAX_SEARCH_K)
    filters: IntentFilters = Field(default_factory=IntentFilters)

    @field_validator("query")
    @classmethod
    def query_has_bounded_normalized_length(cls, value: str) -> str:
        normalized = " ".join(value.lower().split())
        if not normalized:
            raise ValueError("query must not be empty after normalization")
        if len(normalized) > config.MAX_SIGNATURE_CHARS:
            raise ValueError(
                f"normalized query exceeds {config.MAX_SIGNATURE_CHARS} characters"
            )
        return value


class IntentSearchHit(IntentRecord):
    similarity: float


class IntentSearchResponse(StrictModel):
    hits: list[IntentSearchHit]


class ClusterJobCreateRequest(StrictModel):
    min_cluster_size: int = Field(
        default=config.MIN_CLUSTER_SIZE_DEFAULT,
        ge=config.MIN_CLUSTER_SIZE_MIN,
        le=config.MIN_CLUSTER_SIZE_MAX,
    )


ClusterJobStatus = Literal["queued", "running", "completed", "failed"]


class ClusterJob(StrictModel):
    job_id: str
    status: ClusterJobStatus
    min_cluster_size: int
    vector_count: int | None = None
    error_code: str | None = None
    created_by_user_id: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ClusterResult(StrictModel):
    intent_id: str
    input_version: int
    cluster_id: int
    probability: float


class ClusterResultsResponse(StrictModel):
    results: list[ClusterResult]


class HealthResponse(StrictModel):
    status: Literal["ok", "not_ready"]
