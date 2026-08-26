"""Write surface for the insights endpoints: what the extraction worker sends.

Candidates carry no `id`, `inserted_at`, or `expire_at`: the server owns identity,
the clock, and retention.
"""

from __future__ import annotations

import datetime

from pydantic import Field, model_validator

from weave.trace_server.common_interface import BaseModelStrict
from weave.trace_server.insights.enums import InsightSignatureType, InsightWriteGate


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

    `signature_type` says which of `intents` and `failures` is being written; the
    other must be empty. An empty batch is accepted as a no-op, so a worker whose
    candidates were all filtered upstream needs no special case.
    """

    project_id: str = Field(
        description="The ID of the project to write to", examples=["user/project"]
    )
    signature_type: InsightSignatureType = Field(
        description="Which candidate list this call carries, and so which table and "
        "config the request names.",
        examples=["intent"],
    )
    config_sha: str = Field(
        description="Digest of the extraction config the candidates were judged under. "
        "Must equal the digest this deployment resolves for `signature_type`, else "
        "the request is rejected: an unresolvable digest is an unreadable provenance "
        "pointer.",
        examples=["7c1f0b9a2d4e6f8a1b3c5d7e9f0a2b4c6d8e0f1a2b3c4d5e6f7a8b9c0d1e2f3a"],
    )
    intents: list[IntentSignatureCandidate] = Field(
        default_factory=list, description="Empty unless `signature_type` is `intent`."
    )
    failures: list[FailureSignatureCandidate] = Field(
        default_factory=list, description="Empty unless `signature_type` is `failure`."
    )

    @model_validator(mode="after")
    def _only_the_named_type_is_populated(self) -> InsightSignaturesWriteReq:
        unnamed = "failures" if self.signature_type == "intent" else "intents"
        if getattr(self, unnamed):
            raise ValueError(
                f"signature_type is {self.signature_type!r}, so {unnamed} must be empty"
            )
        return self


class InsightSignaturesWriteRes(BaseModelStrict):
    written: int = Field(
        description="Rows that reached the table, after gating and in-batch dedupe. "
        "One request writes one signature type, so one count.",
        examples=[42],
    )
    dropped: dict[InsightWriteGate, int] = Field(
        default_factory=dict,
        description="Gate name to count, for the gates that fired. "
        "`empty_signature`, `vector_dimensions`, `ungrounded_attribution`, and "
        "`duplicate_in_batch` discard the candidate; `unknown_category`, "
        "`unknown_sentiment`, and `unknown_severity` repair the label and keep it. "
        "Neither outcome fails the batch, so callers watch this to catch a drifting "
        "judge.",
        examples=[{"unknown_category": 3, "empty_signature": 1}],
    )
