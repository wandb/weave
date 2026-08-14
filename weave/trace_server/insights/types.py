"""Request and response models for the insights endpoints.

One write surface takes judged turns from the extraction worker; one read surface
returns them as occurrences (`mode="rows"`) or as server-side aggregates
(`mode="groups"`).

Candidates carry no `id`, `inserted_at`, or `expire_at`: the server owns identity,
the clock, and retention.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import Field

from weave.trace_server.common_interface import BaseModelStrict

# Intent rows say what a user was trying to do; failure rows say how an agent
# went wrong. Each read and each write names exactly one.
InsightSignatureType = Literal["intent", "failure"]
InsightQueryMode = Literal["rows", "groups"]
InsightRowOrder = Literal["key", "recent"]
InsightGroupField = Literal[
    "signature", "category", "sentiment", "severity", "agent_name", "day"
]


class InsightSignatureCandidateBase(BaseModelStrict):
    signature: str = Field(
        description="The judge's one-line statement of the intent or failure. Stored "
        "canonicalized (NFKC, collapsed whitespace, no trailing period, casefolded) so "
        "grouping on it groups identity, not phrasing. Empty after canonicalization is "
        "dropped under `empty_signature`.",
        examples=["cancel my subscription and get a refund"],
    )
    category: str = Field(
        description="Taxonomy label from the config named by `config_sha`. An undefined "
        "label is rewritten to `other`, counted under `unknown_category`, and kept.",
        examples=["billing"],
    )
    conversation_id: str = Field(
        description="Conversation the judged turn belongs to.", examples=["conv-9f3c1a"]
    )
    trace_started_at: datetime.datetime = Field(
        description="Start of the judged turn. The time dimension of every read: tables "
        "partition on `toYYYYMM` of it, and `day` is `toDate` of it.",
        examples=["2026-08-14T17:04:31Z"],
    )
    extracted_at: datetime.datetime = Field(
        description="When the judge produced the candidate. Differs from "
        "`trace_started_at` under backfill.",
        examples=["2026-08-14T18:10:02Z"],
    )
    vector: list[float] = Field(
        description="Embedding of the signature, for offline clustering. Length must "
        "equal `embedding.dimensions` of the config named by `config_sha`; any other "
        "length is dropped under `vector_dimensions`.",
        examples=[[0.0131, -0.0042, 0.0781]],
    )
    user_id: str = Field(
        default="", description="Attribution, empty when the caller has none."
    )
    agent_name: str = Field(
        default="",
        description="Agent that served the turn, empty when unknown. Also a `group_by` "
        "field.",
        examples=["support-bot"],
    )
    turn_duration_ms: int = Field(
        default=0,
        description="Duration of the judged turn, denormalized so grouped reads never "
        "join the call tables.",
        examples=[4210],
    )
    turn_cost_usd: float = Field(
        default=0.0,
        description="LLM cost of the judged turn, denormalized. A turn attribute, not "
        "a per-signature cost: several rows off one turn repeat it.",
        examples=[0.0183],
    )


class IntentSignatureCandidate(InsightSignatureCandidateBase):
    trace_id: str = Field(
        description="The judged turn. One turn is one trace.",
        examples=["01936b2c-4f8a-7c1d-9e55-2b6f0a1d4e77"],
    )
    language: str = Field(
        default="und",
        description="Language of the source user text, `und` when undetermined.",
        examples=["en"],
    )
    sentiment: str = Field(
        default="",
        description="Sentiment label from the config. Empty means the judge emitted "
        "none, distinct from a real label such as `neutral`; an undefined label is "
        "blanked and counted under `unknown_sentiment`.",
        examples=["frustrated"],
    )
    sentiment_rationale: str = Field(
        default="",
        description="Justification for `sentiment`. Not filterable or groupable.",
    )


class FailureSignatureCandidate(InsightSignatureCandidateBase):
    """`evidence_span_ids` are span ids, already resolved from the judge's message
    indices: the quote-is-a-substring gate needs the source turn text, so it runs
    in the judge worker and the quotes themselves are never sent here.
    """

    current_trace_id: str = Field(
        description="Turn where the failure surfaced. Must also appear in "
        "`affected_trace_ids`, else the candidate is dropped under "
        "`ungrounded_attribution`.",
        examples=["01936b2c-4f8a-7c1d-9e55-2b6f0a1d4e77"],
    )
    affected_trace_ids: list[str] = Field(
        description="Every turn the failure implicates, including `current_trace_id`. "
        "Deduplicated and sorted on insert. A `trace_id` read filter matches membership "
        "here, so a turn that only inherited the failure still matches.",
        examples=[["01936b2c-4f8a-7c1d-9e55-2b6f0a1d4e77", "01936b31-77c0-7a02-83d1"]],
    )
    evidence_span_ids: list[str] = Field(
        default_factory=list,
        description="Spans the judge cited. Deduplicated and sorted on insert.",
    )
    failure_reason: str = Field(
        default="",
        description="The judge's explanation. Not filterable or groupable.",
    )
    severity: str = Field(
        default="",
        description="Severity label from the config. Empty means the judge emitted "
        "none; an undefined label is blanked and counted under `unknown_severity`.",
        examples=["high"],
    )


class InsightSignaturesWriteReq(BaseModelStrict):
    """One call carries one signature type, because `config_sha` names one config file.

    `intents` and `failures` are mutually exclusive: the intent and failure
    configs have different digests, so a request holding both could not state
    which config its rows point at.
    """

    project_id: str = Field(
        description="The ID of the project to write to", examples=["user/project"]
    )
    config_sha: str = Field(
        description="Digest of the extraction config the candidates were judged under. "
        "Must equal the digest this deployment resolves for the signature type, else "
        "the request is rejected: an unresolvable digest is an unreadable provenance "
        "pointer.",
        examples=["7c1f0b9a2d4e6f8a1b3c5d7e9f0a2b4c6d8e0f1a2b3c4d5e6f7a8b9c0d1e2f3a"],
    )
    intents: list[IntentSignatureCandidate] = Field(
        default_factory=list, description="Empty when writing failures."
    )
    failures: list[FailureSignatureCandidate] = Field(
        default_factory=list, description="Empty when writing intents."
    )


class InsightWriteCounts(BaseModelStrict):
    intents: int = Field(default=0, description="Intent rows inserted.", examples=[42])
    failures: int = Field(default=0, description="Failure rows inserted.", examples=[7])


class InsightSignaturesWriteRes(BaseModelStrict):
    written: InsightWriteCounts = Field(
        description="Rows that reached the table, after gating and in-batch dedupe."
    )
    dropped: dict[str, int] = Field(
        default_factory=dict,
        description="Gate name to count, for the gates that fired. "
        "`empty_signature`, `vector_dimensions`, `ungrounded_attribution`, and "
        "`duplicate_in_batch` discard the candidate; `unknown_category`, "
        "`unknown_sentiment`, and `unknown_severity` repair the label and keep it. "
        "Neither outcome fails the batch, so callers watch this to catch a drifting "
        "judge.",
        examples=[{"unknown_category": 3, "empty_signature": 1}],
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


class InsightSignatureRow(BaseModelStrict):
    """One judged occurrence: one signature, one turn.

    Nothing collapses re-extractions, so a turn judged twice is two rows. The
    signature-type-specific fields are optional on one model because
    `signature_type` on the request already says which half is populated.
    """

    id: uuid.UUID = Field(
        description="Server-minted UUIDv7, the tiebreaker in `order='key'` paging.",
        examples=["01936b2c-4f8a-7c1d-9e55-2b6f0a1d4e77"],
    )
    signature: str = Field(description="Canonicalized signature text.")
    signature_hash: str = Field(
        description="Uppercase `hex(sipHash128(signature))`, computed by ClickHouse so "
        "clustering jobs join on it without reimplementing the hash. Pass back in "
        "`signature_hashes`.",
        examples=["9F2C41B8D0E37A5641C0B9E8D7A62F13"],
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

    trace_id: str | None = Field(default=None, description="Intent only: judged turn.")
    sentiment: str | None = Field(
        default=None, description="Intent only: sentiment label, post-repair."
    )
    current_trace_id: str | None = Field(
        default=None, description="Failure only: turn where the failure surfaced."
    )
    affected_trace_ids: list[str] | None = Field(
        default=None, description="Failure only: every turn implicated."
    )
    evidence_span_ids: list[str] | None = Field(
        default=None, description="Failure only: spans the judge cited."
    )
    failure_reason: str | None = Field(
        default=None, description="Failure only: the judge's explanation."
    )
    severity: str | None = Field(
        default=None, description="Failure only: severity label, post-repair."
    )

    vector: list[float] | None = Field(
        default=None, description="Present only when `include_vector` was requested."
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
        "for facet and overview surfaces; it ignores `order`, `cursor`, and "
        "`include_vector`.",
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
    signature_hashes: list[str] | None = Field(
        default=None,
        description="Restrict to these `signature_hash` values, case-insensitive. The "
        "way to fetch the occurrences behind an offline cluster.",
        examples=[["9F2C41B8D0E37A5641C0B9E8D7A62F13"]],
    )

    include_vector: bool = Field(
        default=False,
        description="`rows` only. Off by default because the embedding dwarfs the rest "
        "of the row.",
    )
    order: InsightRowOrder = Field(
        default="recent",
        description="`rows` only. `recent` sorts newest turn first, for feeds. `key` "
        "sorts by `(day, id)` ascending, a total order stable under new writes and the "
        "only one `cursor` pages.",
        examples=["recent", "key"],
    )
    cursor: InsightSignatureCursor | None = Field(
        default=None,
        description="Resume position from a previous `next_cursor`. Honored only with "
        "`mode='rows'` and `order='key'`.",
    )

    group_by: list[InsightGroupField] = Field(
        default_factory=lambda: ["signature"],
        description="`groups` only: the facets to aggregate on. `day` buckets by "
        "`toDate(trace_started_at)`. `sentiment` is intent-only and `severity` "
        "failure-only; the wrong pairing is an error, not an empty column.",
        examples=[["signature"], ["category", "day"]],
    )

    limit: int = Field(
        default=100,
        description="Rows per page in `rows`; number of top groups in `groups`.",
        examples=[100],
    )


class InsightSignaturesQueryRes(BaseModelStrict):
    rows: list[InsightSignatureRow] = Field(
        default_factory=list, description="Populated in `rows` mode."
    )
    groups: list[InsightSignatureGroup] = Field(
        default_factory=list, description="Populated in `groups` mode."
    )
    next_cursor: InsightSignatureCursor | None = Field(
        default=None,
        description="Pass back as `cursor` for the next page. Set only for "
        "`mode='rows'` with `order='key'`, and `None` once a page comes back empty.",
    )
