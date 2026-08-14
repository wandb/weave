"""Request and response models for the insights endpoints.

Candidates carry no `id`, `inserted_at`, or `expire_at`: the server owns identity,
the clock, and retention.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import Field

from weave.trace_server.common_interface import BaseModelStrict

InsightSignatureType = Literal["intent", "failure"]
InsightQueryMode = Literal["rows", "groups"]
InsightRowOrder = Literal["key", "recent"]
InsightGroupField = Literal[
    "signature", "category", "sentiment", "severity", "agent_name", "day"
]


class IntentSignatureCandidate(BaseModelStrict):
    signature: str
    category: str
    conversation_id: str
    trace_id: str
    trace_started_at: datetime.datetime
    extracted_at: datetime.datetime
    vector: list[float]
    language: str = "und"
    sentiment: str = ""
    sentiment_rationale: str = ""
    user_id: str = ""
    agent_name: str = ""
    turn_duration_ms: int = 0
    turn_cost_usd: float = 0.0


class FailureSignatureCandidate(BaseModelStrict):
    """`evidence_span_ids` are span ids, already resolved from the judge's message
    indices: the quote-is-a-substring gate needs the source turn text, so it runs
    in the judge worker and the quotes themselves are never sent here.
    """

    signature: str
    category: str
    conversation_id: str
    current_trace_id: str
    affected_trace_ids: list[str]
    trace_started_at: datetime.datetime
    extracted_at: datetime.datetime
    vector: list[float]
    evidence_span_ids: list[str] = Field(default_factory=list)
    failure_reason: str = ""
    severity: str = ""
    user_id: str = ""
    agent_name: str = ""
    turn_duration_ms: int = 0
    turn_cost_usd: float = 0.0


class InsightSignaturesWriteReq(BaseModelStrict):
    """One call carries one signature type, because `config_sha` names one config file.

    `intents` and `failures` are mutually exclusive: the intent and failure
    configs have different digests, so a request holding both could not state
    which config its rows point at.
    """

    project_id: str
    config_sha: str
    intents: list[IntentSignatureCandidate] = Field(default_factory=list)
    failures: list[FailureSignatureCandidate] = Field(default_factory=list)


class InsightWriteCounts(BaseModelStrict):
    intents: int = 0
    failures: int = 0


class InsightSignaturesWriteRes(BaseModelStrict):
    """`dropped` maps gate name to count.

    Candidate gates discard malformed rows; taxonomy gates repair the label and
    keep the row. Neither outcome fails the surrounding batch.
    """

    written: InsightWriteCounts
    dropped: dict[str, int] = Field(default_factory=dict)


class InsightSignatureCursor(BaseModelStrict):
    day: datetime.date
    id: uuid.UUID


class InsightSignatureRow(BaseModelStrict):
    """The signature-type-specific fields are optional on one model because
    `signature_type` on the request already says which half is populated.
    """

    id: uuid.UUID
    signature: str
    signature_hash: str
    category: str
    conversation_id: str
    user_id: str
    agent_name: str
    turn_duration_ms: int
    turn_cost_usd: float
    trace_started_at: datetime.datetime
    inserted_at: datetime.datetime

    trace_id: str | None = None
    sentiment: str | None = None
    current_trace_id: str | None = None
    affected_trace_ids: list[str] | None = None
    evidence_span_ids: list[str] | None = None
    failure_reason: str | None = None
    severity: str | None = None

    vector: list[float] | None = None


class InsightSignatureGroup(BaseModelStrict):
    keys: dict[str, str]
    occurrences: int
    conversations: int
    users: int
    modal_category: str
    avg_turn_cost_usd: float
    p50_turn_duration_ms: float
    configs: list[str]


class InsightSignaturesQueryReq(BaseModelStrict):
    """`day_start` / `day_end` are required: the tables partition on
    `toYYYYMM(trace_started_at)`, so an unbounded read opens every partition.
    """

    project_id: str
    signature_type: InsightSignatureType
    day_start: datetime.date
    day_end: datetime.date
    mode: InsightQueryMode = "rows"

    trace_id: str | None = None
    conversation_id: str | None = None
    categories: list[str] | None = None
    signature_hashes: list[str] | None = None

    include_vector: bool = False
    order: InsightRowOrder = "recent"
    cursor: InsightSignatureCursor | None = None

    group_by: list[InsightGroupField] = Field(default_factory=lambda: ["signature"])

    limit: int = 100


class InsightSignaturesQueryRes(BaseModelStrict):
    rows: list[InsightSignatureRow] = Field(default_factory=list)
    groups: list[InsightSignatureGroup] = Field(default_factory=list)
    next_cursor: InsightSignatureCursor | None = None
    # False on the failure signature type: two failures in one conversation can
    # share a turn, so cost and duration overlap and must not be summed.
    cost_is_additive: bool = True
