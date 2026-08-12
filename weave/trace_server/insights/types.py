"""Request and response models for the insights endpoints.

Candidates carry no `id`, `inserted_at`, or `expire_at`: the server owns identity,
the clock, and retention.
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import Field

from weave.trace_server.common_interface import BaseModelStrict

InsightLens = Literal["intent", "failure"]
InsightQueryMode = Literal["rows", "groups"]
InsightRowOrder = Literal["key", "recent"]
InsightGroupField = Literal[
    "signature", "category", "sentiment", "severity", "agent_name", "day"
]

# `sentiment_confidence` sentinel for "the judge reported none", matching the
# column default. Zero is a real confidence, so it cannot mean absent.
NO_CONFIDENCE = -1.0


class IntentSignatureCandidate(BaseModelStrict):
    """One judged intent, before canonicalization and identity.

    `signature` is the judge's exact wording. The writer canonicalizes it into
    the `signature` column and keeps this wording in `signature_display`.
    """

    signature: str
    category: str
    conversation_id: str
    turn_trace_id: str
    source_started_at: datetime.datetime
    extracted_at: datetime.datetime
    vector: list[float]
    language: str = "und"
    sentiment: str = ""
    sentiment_rationale: str = ""
    sentiment_confidence: float = NO_CONFIDENCE
    user_id: str = ""
    agent_name: str = ""
    duration_ms: int = 0
    cost_usd: float = 0.0


class FailureSignatureCandidate(BaseModelStrict):
    """One judged failure, anchored on the turn it started in.

    `evidence_span_ids` arrives already resolved: the judge cites message
    indices, and only the worker holding the source turn can turn those into
    span ids, so that resolution never happens here.
    """

    signature: str
    category: str
    conversation_id: str
    onset_turn_trace_id: str
    turn_trace_ids: list[str]
    source_started_at: datetime.datetime
    extracted_at: datetime.datetime
    vector: list[float]
    failure_reason: str = ""
    severity: str = ""
    evidence_span_ids: list[str] = Field(default_factory=list)
    user_id: str = ""
    agent_name: str = ""
    duration_ms: int = 0
    cost_usd: float = 0.0


class InsightSignaturesWriteReq(BaseModelStrict):
    """One call carries one space, because `config_sha` names one config file.

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
    """`dropped` maps gate name to count. A dropped candidate is never an error:
    inserts are batched, so raising would fail 255 good rows for one bad one.
    """

    written: InsightWriteCounts
    dropped: dict[str, int] = Field(default_factory=dict)


class InsightContextSignature(BaseModelStrict):
    """One already-distilled signature, attributed to one turn.

    A failure spanning three turns is context for all three, so it appears once
    per requested turn it was attributed to.
    """

    lens: InsightLens
    turn_trace_id: str
    signature: str
    signature_display: str
    category: str
    config_sha: str
    source_started_at: datetime.datetime


class InsightContextQueryReq(BaseModelStrict):
    """The distilled history for a named set of turns.

    The caller passes the turns because only it can enumerate them: 10% of turns
    produce no intent and most produce no failure, so the signature tables cannot
    say which turns a conversation has. `day_start` / `day_end` are required for
    the same reason they are on the signatures query.
    """

    project_id: str
    conversation_id: str
    turn_trace_ids: list[str]
    day_start: datetime.date
    day_end: datetime.date


class InsightContextQueryRes(BaseModelStrict):
    """Flat and unordered by turn: the caller already holds the turn order, and
    this endpoint cannot derive it because the data model carries no turn ordinal.
    """

    signatures: list[InsightContextSignature] = Field(default_factory=list)


class InsightSignatureCursor(BaseModelStrict):
    day: datetime.date
    id: str


class InsightSignatureRow(BaseModelStrict):
    """The lens-specific fields are optional on one model because `lens` on the
    request already says which half is populated.
    """

    id: str
    signature: str
    signature_display: str
    signature_hash: str
    category: str
    conversation_id: str
    user_id: str
    agent_name: str
    duration_ms: int
    cost_usd: float
    source_started_at: datetime.datetime
    inserted_at: datetime.datetime

    turn_trace_id: str | None = None
    language: str | None = None
    sentiment: str | None = None
    sentiment_confidence: float | None = None
    onset_turn_trace_id: str | None = None
    turn_trace_ids: list[str] | None = None
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
    avg_cost_usd: float
    p50_duration_ms: float
    configs: list[str]


class InsightSignaturesQueryReq(BaseModelStrict):
    """`day_start` / `day_end` are required: the tables partition on
    `toYYYYMM(source_started_at)`, so an unbounded read opens every partition.
    """

    project_id: str
    lens: InsightLens
    day_start: datetime.date
    day_end: datetime.date
    mode: InsightQueryMode = "rows"

    turn_trace_id: str | None = None
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
    # False on the failure lens: two failures in one conversation can share a
    # turn, so cost and duration overlap and must not be summed.
    cost_is_additive: bool = True
