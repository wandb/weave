"""Writer gates for the signature tables. The database enforces nothing.

Migration 041 carries no CHECK constraints and no Enums because inserts are
batched: one bad candidate would fail a batch of 256. Every gate drops the
candidate and counts it, and the counters are the pipeline's precision signal.

No `id` is written. The tables mint it with `generateUUIDv7()`, so identity is
the server's and a row is never silently replaced by a re-extraction.
`signature_hash` is likewise absent: it must equal ClickHouse's
`sipHash128(signature)` to join the cluster tables, so only a `SELECT` produces it.
"""

from __future__ import annotations

import unicodedata
from functools import cache

from weave.trace_server.insights import config
from weave.trace_server.insights.types import (
    FailureSignatureCandidate,
    IntentSignatureCandidate,
)

GATE_UNGROUNDED_ATTRIBUTION = "ungrounded_attribution"
GATE_EMPTY_SIGNATURE = "empty_signature"
GATE_VECTOR_DIMENSIONS = "vector_dimensions"
GATE_UNKNOWN_CATEGORY = "unknown_category"
GATE_UNKNOWN_SENTIMENT = "unknown_sentiment"
GATE_UNKNOWN_SEVERITY = "unknown_severity"
GATE_DUPLICATE_IN_BATCH = "duplicate_in_batch"

FALLBACK_LABEL = "other"
UNKNOWN_LANGUAGE = "und"

Row = dict[str, object]
Dropped = dict[str, int]
# One judged occurrence: the turn it came from plus what was claimed about it.
DedupeKey = tuple[str, str, str]


class InsightWriteRejected(Exception):
    """The request as a whole is unusable, as opposed to one bad candidate."""


def validate_config_sha(signature_type: str, claimed: str) -> None:
    """Require the caller to agree with the deployed config.

    A row points at its config by digest, so a digest this deployment cannot
    resolve would be an unreadable provenance pointer.
    """
    actual = config.config_sha(_load(signature_type))
    if claimed != actual:
        raise InsightWriteRejected(
            f"{signature_type} config_sha {claimed!r} does not match the deployed "
            f"config {actual!r}"
        )


def canonicalize_signature(text: str, *, normalization_version: int) -> str:
    """The stored form, so `GROUP BY signature` groups identity.

    Versioned by the config's `normalization_version`, which lives inside
    `config_sha`, so changing it is a visible digest move.
    """
    if normalization_version != 1:
        raise InsightWriteRejected(
            f"unsupported normalization_version {normalization_version}"
        )
    collapsed = " ".join(unicodedata.normalize("NFKC", text).split())
    return collapsed.rstrip(".").strip().casefold()


def prepare_intents(
    project_id: str,
    config_sha: str,
    candidates: list[IntentSignatureCandidate],
) -> tuple[list[Row], Dropped]:
    cfg = _intent_config()
    categories = _label_names(cfg.extraction.taxonomy)
    sentiments = _label_names(cfg.extraction.sentiment)
    dropped: Dropped = {}
    rows: dict[DedupeKey, Row] = {}

    for candidate in candidates:
        signature = canonicalize_signature(
            candidate.signature,
            normalization_version=cfg.extraction.normalization_version,
        )
        if not _accepts(signature, candidate.vector, cfg.embedding.dimensions, dropped):
            continue
        key = (candidate.conversation_id, candidate.trace_id, signature)
        _note_duplicate(rows, key, dropped)
        rows[key] = {
            "project_id": project_id,
            "config_sha": config_sha,
            "signature": signature,
            "category": _label(
                candidate.category, categories, dropped, GATE_UNKNOWN_CATEGORY
            ),
            "language": candidate.language or UNKNOWN_LANGUAGE,
            "sentiment": _optional_label(
                candidate.sentiment, sentiments, dropped, GATE_UNKNOWN_SENTIMENT
            ),
            "sentiment_rationale": candidate.sentiment_rationale,
            "vector": candidate.vector,
            "conversation_id": candidate.conversation_id,
            "trace_id": candidate.trace_id,
            "user_id": candidate.user_id,
            "agent_name": candidate.agent_name,
            "turn_duration_ms": candidate.turn_duration_ms,
            "turn_cost_usd": candidate.turn_cost_usd,
            "trace_started_at": candidate.trace_started_at,
            "extracted_at": candidate.extracted_at,
        }
    return list(rows.values()), dropped


def prepare_failures(
    project_id: str,
    config_sha: str,
    candidates: list[FailureSignatureCandidate],
) -> tuple[list[Row], Dropped]:
    cfg = _failure_config()
    categories = _label_names(cfg.extraction.taxonomy)
    severities = _label_names(cfg.extraction.severity)
    dropped: Dropped = {}
    rows: dict[DedupeKey, Row] = {}

    for candidate in candidates:
        signature = canonicalize_signature(
            candidate.signature,
            normalization_version=cfg.extraction.normalization_version,
        )
        if not _accepts(signature, candidate.vector, cfg.embedding.dimensions, dropped):
            continue
        # Sorted and deduplicated so two extractions of one failure compare equal,
        # with the current turn a member so the row is attributable.
        affected = sorted(set(candidate.affected_trace_ids))
        if candidate.current_trace_id not in affected:
            _count(dropped, GATE_UNGROUNDED_ATTRIBUTION)
            continue
        key = (candidate.conversation_id, candidate.current_trace_id, signature)
        _note_duplicate(rows, key, dropped)
        rows[key] = {
            "project_id": project_id,
            "config_sha": config_sha,
            "signature": signature,
            "failure_reason": candidate.failure_reason,
            "category": _label(
                candidate.category, categories, dropped, GATE_UNKNOWN_CATEGORY
            ),
            "severity": _optional_label(
                candidate.severity, severities, dropped, GATE_UNKNOWN_SEVERITY
            ),
            "vector": candidate.vector,
            "conversation_id": candidate.conversation_id,
            "current_trace_id": candidate.current_trace_id,
            "affected_trace_ids": affected,
            "evidence_span_ids": sorted(set(candidate.evidence_span_ids)),
            "user_id": candidate.user_id,
            "agent_name": candidate.agent_name,
            "turn_duration_ms": candidate.turn_duration_ms,
            "turn_cost_usd": candidate.turn_cost_usd,
            "trace_started_at": candidate.trace_started_at,
            "extracted_at": candidate.extracted_at,
        }
    return list(rows.values()), dropped


@cache
def _load(signature_type: str) -> config.SignatureConfig:
    """Configs are checked in, so parsing them once per process is enough."""
    return config.load_config(signature_type)


def _intent_config() -> config.IntentConfig:
    cfg = _load("intent")
    if not isinstance(cfg, config.IntentConfig):
        raise InsightWriteRejected("intent.yaml does not declare the intent type")
    return cfg


def _failure_config() -> config.FailureConfig:
    cfg = _load("failure")
    if not isinstance(cfg, config.FailureConfig):
        raise InsightWriteRejected("failure.yaml does not declare the failure type")
    return cfg


def _label_names(taxonomy: config.TaxonomyRef) -> set[str]:
    return {label.name for label in taxonomy.labels()}


def _accepts(
    signature: str, vector: list[float], dimensions: int, dropped: Dropped
) -> bool:
    if not signature:
        _count(dropped, GATE_EMPTY_SIGNATURE)
        return False
    if len(vector) != dimensions:
        _count(dropped, GATE_VECTOR_DIMENSIONS)
        return False
    return True


def _label(value: str, allowed: set[str], dropped: Dropped, gate: str) -> str:
    if value in allowed:
        return value
    _count(dropped, gate)
    return FALLBACK_LABEL


def _optional_label(value: str, allowed: set[str], dropped: Dropped, gate: str) -> str:
    """`''` records that no usable label came back, which is why an unknown one
    does not fall back to a real label: `''` is not `neutral` and not `info`.
    """
    if not value or value in allowed:
        return value
    _count(dropped, gate)
    return ""


def _note_duplicate(
    rows: dict[DedupeKey, Row], key: DedupeKey, dropped: Dropped
) -> None:
    if key in rows:
        _count(dropped, GATE_DUPLICATE_IN_BATCH)


def _count(dropped: Dropped, gate: str) -> None:
    dropped[gate] = dropped.get(gate, 0) + 1
