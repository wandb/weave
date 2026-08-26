"""Read surface for the insights endpoints.

One filter surface over two result shapes: occurrences (`mode="rows"`) or
server-side aggregates (`mode="groups"`).
"""

from __future__ import annotations

import datetime
import uuid

from pydantic import Field, model_validator

from weave.trace_server.common_interface import BaseModelStrict
from weave.trace_server.insights.enums import (
    DEFAULT_SIGNATURE_LIMIT,
    GROUPS_ONLY_FIELDS,
    MAX_SIGNATURE_LIMIT,
    MAX_VECTOR_PAGE_LIMIT,
    ROWS_ONLY_FIELDS,
    InsightGroupField,
    InsightQueryMode,
    InsightRowOrder,
    InsightSignatureType,
)


class InsightSignatureCursor(BaseModelStrict):
    """Keyset position, echoed back to resume a `mode="rows"`, `order="key"` walk."""

    day: datetime.date = Field(
        description="`toDate(trace_started_at)` of the last row returned.",
        examples=["2026-08-14"],
    )
    id: uuid.UUID = Field(
        description="Id of the last row returned.",
        examples=["01936b2c-4f8a-7c1d-9e55-2b6f0a1d4e77"],
    )


class InsightSignatureRowBase(BaseModelStrict):
    """What one judged occurrence carries whatever the signature type.

    `id` is derived from `(project_id, config_sha, conversation_id, turn, signature)`,
    so re-judging a turn under the same config replaces the row it produced before
    and a retried write is a no-op rather than a second occurrence.
    """

    id: uuid.UUID = Field(
        description="Deterministic UUIDv5, and the tiebreaker in `order='key'` paging.",
        examples=["01936b2c-4f8a-7c1d-9e55-2b6f0a1d4e77"],
    )
    signature: str = Field(
        description="Canonicalized signature text. Pass back in `signatures` to fetch "
        "the occurrences behind an offline cluster."
    )
    category: str = Field(description="Taxonomy label, post-repair.")
    conversation_id: str = Field(description="Conversation the judged turn belongs to.")
    user_id: str = Field(description="Attribution, empty when unknown.")
    agent_name: str = Field(
        description="Agent that served the turn, empty when unknown."
    )
    turn_duration_ms: int = Field(description="Duration of the judged turn.")
    turn_cost_usd: float = Field(description="LLM cost of the judged turn.")
    trace_started_at: datetime.datetime = Field(description="Start of the judged turn.")
    inserted_at: datetime.datetime = Field(description="When the server wrote the row.")
    vector: list[float] | None = Field(
        default=None, description="Present only when `include_vector` was requested."
    )


class IntentSignatureRow(InsightSignatureRowBase):
    trace_id: str = Field(description="The judged turn.")
    language: str = Field(description="Language of the source user text.")
    sentiment: str = Field(
        description="Sentiment label, post-repair. Empty means the judge emitted none."
    )


class FailureSignatureRow(InsightSignatureRowBase):
    current_trace_id: str = Field(description="Turn where the failure surfaced.")
    affected_trace_ids: list[str] = Field(description="Every turn implicated.")
    evidence_span_ids: list[str] = Field(description="Spans the judge cited.")
    failure_reason: str = Field(description="The judge's explanation.")
    severity: str = Field(
        description="Severity label, post-repair. Empty means the judge emitted none."
    )


class InsightSignatureGroup(BaseModelStrict):
    """One distinct `group_by` combination, aggregated over the query's window.

    A turn emits several signatures, so the turn-scoped measures below count each
    turn once while `occurrences`, `modal_category`, and `configs` count each row.
    """

    keys: dict[str, str] = Field(
        description="`group_by` field names to this group's values.",
        examples=[{"category": "billing", "day": "2026-08-14"}],
    )
    occurrences: int = Field(
        description="Rows in the group: signatures emitted, not turns or "
        "conversations.",
        examples=[1284],
    )
    turns: int = Field(
        description="Distinct turns in the group. The denominator of "
        "`avg_turn_cost_usd` and `p50_turn_duration_ms`.",
        examples=[1102],
    )
    conversations: int = Field(
        description="Distinct conversations. Against `occurrences`, separates a broad "
        "signature from a repetitive one.",
        examples=[903],
    )
    users: int = Field(
        description="Distinct users, counting the empty `user_id` as one value.",
        examples=[411],
    )
    modal_category: str = Field(
        description="Most frequent category, since one signature can straddle "
        "categories.",
        examples=["billing"],
    )
    avg_turn_cost_usd: float = Field(
        description="Mean cost of a turn in the group, over `turns`.",
        examples=[0.0212],
    )
    p50_turn_duration_ms: float = Field(
        description="Median duration of a turn in the group, over `turns`.",
        examples=[3980.0],
    )
    configs: list[str] = Field(
        description="Up to three `config_sha` values that produced the group, so a "
        "group spanning a config change is visible rather than silently mixed."
    )


class InsightSignaturesQueryReq(BaseModelStrict):
    """`day_start` / `day_end` are required: the tables partition on
    `toYYYYMM(trace_started_at)`, so an unbounded read opens every partition.
    """

    project_id: str = Field(
        description="The ID of the project to query", examples=["user/project"]
    )
    signature_type: InsightSignatureType = Field(
        description="Which table to read. No union across the two.",
        examples=["intent"],
    )
    day_start: datetime.date = Field(
        description="Window start, inclusive, on `toDate(trace_started_at)`.",
        examples=["2026-08-01"],
    )
    day_end: datetime.date = Field(
        description="Window end, inclusive.", examples=["2026-08-14"]
    )
    mode: InsightQueryMode = Field(
        default="rows",
        description="Result shape over the same window and filters. `rows` returns one "
        "record per occurrence into `rows`, for drilldown and vector export, and is the "
        "only mode that pages. `groups` returns one record per distinct `group_by` "
        "combination into `groups`, aggregated server-side and ranked by occurrences, "
        "for facet and overview surfaces. Naming a field the chosen mode does not read "
        "is an error rather than a silent no-op.",
        examples=["rows", "groups"],
    )

    trace_id: str | None = Field(
        default=None,
        description="Restrict to one turn. Matches `trace_id` on intents, membership in "
        "`affected_trace_ids` on failures.",
    )
    conversation_id: str | None = Field(
        default=None, description="Restrict to one conversation."
    )
    categories: list[str] | None = Field(
        default=None,
        description="Restrict to these taxonomy labels.",
        examples=[["billing", "account_management"]],
    )
    signatures: list[str] | None = Field(
        default=None,
        description="Restrict to these canonicalized signatures. The way to fetch the "
        "occurrences behind an offline cluster.",
        examples=[["cancel my subscription and get a refund"]],
    )

    include_vector: bool = Field(
        default=False,
        description="`rows` only. Off by default because the embedding dwarfs the rest "
        f"of the row, and caps `limit` at {MAX_VECTOR_PAGE_LIMIT}.",
    )
    order: InsightRowOrder = Field(
        default="recent",
        description="`rows` only. `recent` sorts newest turn first, for feeds. `key` "
        "sorts by `(day, id)` ascending, a total order over the rows already written "
        "and the only one `cursor` pages.",
        examples=["recent", "key"],
    )
    cursor: InsightSignatureCursor | None = Field(
        default=None,
        description="Resume position from a previous `next_cursor`. Requires "
        "`order='key'`.",
    )

    group_by: list[InsightGroupField] = Field(
        default_factory=lambda: ["signature"],
        description="`groups` only: the facets to aggregate on. `day` buckets by "
        "`toDate(trace_started_at)`. `sentiment` is intent-only and `severity` "
        "failure-only; the wrong pairing is an error, not an empty column.",
        examples=[["signature"], ["category", "day"]],
    )

    limit: int = Field(
        default=DEFAULT_SIGNATURE_LIMIT,
        ge=1,
        le=MAX_SIGNATURE_LIMIT,
        description="Rows per page in `rows`; number of top groups in `groups`.",
        examples=[100],
    )

    @model_validator(mode="after")
    def _coherent_query(self) -> InsightSignaturesQueryReq:
        if self.day_start > self.day_end:
            raise ValueError(
                f"day_start {self.day_start} is after day_end {self.day_end}"
            )
        unread = ROWS_ONLY_FIELDS if self.mode == "groups" else GROUPS_ONLY_FIELDS
        named = sorted(unread & self.model_fields_set)
        if named:
            raise ValueError(f"mode={self.mode!r} does not read {', '.join(named)}")
        if self.cursor is not None and self.order != "key":
            raise ValueError(f"cursor requires order='key', got {self.order!r}")
        if self.include_vector and self.limit > MAX_VECTOR_PAGE_LIMIT:
            raise ValueError(
                f"include_vector caps limit at {MAX_VECTOR_PAGE_LIMIT}, got {self.limit}"
            )
        if not self.group_by:
            raise ValueError("group_by needs at least one field")
        return self


class InsightSignaturesQueryRes(BaseModelStrict):
    rows: list[IntentSignatureRow] | list[FailureSignatureRow] = Field(
        default_factory=list,
        description="Populated in `rows` mode, with the row type `signature_type` named.",
    )
    groups: list[InsightSignatureGroup] = Field(
        default_factory=list, description="Populated in `groups` mode."
    )
    next_cursor: InsightSignatureCursor | None = Field(
        default=None,
        description="Pass back as `cursor` for the next page. Set only for "
        "`mode='rows'` with `order='key'`, and `None` as soon as a page comes back "
        "short of `limit`, so a walk ends without an extra empty request.",
    )
