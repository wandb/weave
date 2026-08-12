"""Writer gates for the signature tables. The database enforces nothing.

Migration 040 carries no CHECK constraints and no Enums because inserts are
batched: one bad candidate would fail a batch of 256. Every gate drops the
candidate and counts it, and the counters are the pipeline's precision signal.

`signature_hash` is deliberately absent: it must equal ClickHouse's
`sipHash128(signature)` to join the cluster tables, so only a `SELECT` produces it.
"""

from __future__ import annotations

import datetime
import hashlib
import unicodedata
import uuid

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
# A UUID is 128 bits, so the digest is sized to fill one exactly.
ID_DIGEST_BYTES = 16

Row = dict[str, object]
Dropped = dict[str, int]


class InsightWriteRejected(Exception):
    """The request as a whole is unusable, as opposed to one bad candidate."""


def intent_config() -> config.IntentConfig:
    """The intent space's config, narrowed to the model that declares sentiment."""
    loaded = config.load_config("intent")
    if not isinstance(loaded, config.IntentConfig):
        raise InsightWriteRejected("intent config did not validate as an intent config")
    return loaded


def failure_config() -> config.FailureConfig:
    """The failure space's config, narrowed to the model that declares severity."""
    loaded = config.load_config("failure")
    if not isinstance(loaded, config.FailureConfig):
        raise InsightWriteRejected(
            "failure config did not validate as a failure config"
        )
    return loaded


def validate_config_sha(space: str, claimed: str) -> None:
    """Require the caller to agree with the deployed config.

    A row points at its config by digest, so a digest this deployment cannot
    resolve would be an unreadable provenance pointer.
    """
    actual = config.config_sha(config.load_config(space))
    if claimed != actual:
        raise InsightWriteRejected(
            f"{space} config_sha {claimed!r} does not match the deployed "
            f"config {actual!r}"
        )


def canonicalize_signature(text: str, *, normalization_version: int) -> str:
    """The stored `signature`, so `GROUP BY signature` groups identity.

    Lossy on purpose. The judge's own wording is kept in `signature_display`, so
    nothing readable is lost by folding case and trailing punctuation here.
    Versioned by the config's `normalization_version`, which lives inside
    `config_sha`, so changing it is a visible digest move.
    """
    if normalization_version != 1:
        raise InsightWriteRejected(
            f"unsupported normalization_version {normalization_version}"
        )
    collapsed = " ".join(unicodedata.normalize("NFKC", text).split())
    return collapsed.rstrip(".").strip().casefold()


def signature_id(
    project_id: str,
    conversation_id: str,
    anchor_turn_trace_id: str,
    canonical_signature: str,
    source_started_at: datetime.datetime,
) -> uuid.UUID:
    """Replacement identity for one signature row.

    Content-addressed rather than random, so a re-extraction replaces its row
    instead of duplicating it. The `id` column is a UUID, which is exactly the
    128 bits this digest produces; the result is a hash rather than an RFC 4122
    UUID, and nothing reads a version out of it.

    The source day is folded in because it precedes `id` in the sorting key: a
    re-extraction whose snapshot drifted across midnight must produce a visibly
    new id rather than a silent duplicate.
    """
    parts = (
        project_id,
        conversation_id,
        anchor_turn_trace_id,
        canonical_signature,
        source_started_at.date().isoformat(),
    )
    joined = "\x00".join(parts).encode("utf-8")
    digest = hashlib.blake2b(joined, digest_size=ID_DIGEST_BYTES).digest()
    return uuid.UUID(bytes=digest)


def prepare_intents(
    project_id: str,
    config_sha: str,
    candidates: list[IntentSignatureCandidate],
) -> tuple[list[Row], Dropped]:
    cfg = intent_config()
    categories = set(cfg.extraction.taxonomy.labels())
    sentiments = set(cfg.extraction.sentiment.labels())
    dimensions = cfg.embedding.dimensions
    normalization = cfg.extraction.normalization_version
    dropped: Dropped = {}
    rows: dict[uuid.UUID, Row] = {}

    for candidate in candidates:
        signature = canonicalize_signature(
            candidate.signature, normalization_version=normalization
        )
        if not _accepts(signature, candidate.vector, dimensions, dropped):
            continue
        row_id = signature_id(
            project_id,
            candidate.conversation_id,
            candidate.turn_trace_id,
            signature,
            candidate.source_started_at,
        )
        _note_duplicate(rows, row_id, dropped)
        rows[row_id] = {
            "project_id": project_id,
            "id": row_id,
            "config_sha": config_sha,
            "signature": signature,
            "signature_display": candidate.signature.strip(),
            "category": _label(
                candidate.category, categories, dropped, GATE_UNKNOWN_CATEGORY
            ),
            "language": candidate.language or UNKNOWN_LANGUAGE,
            "sentiment": _optional_label(
                candidate.sentiment, sentiments, dropped, GATE_UNKNOWN_SENTIMENT
            ),
            "sentiment_rationale": candidate.sentiment_rationale,
            "sentiment_confidence": candidate.sentiment_confidence,
            "vector": candidate.vector,
            "conversation_id": candidate.conversation_id,
            "turn_trace_id": candidate.turn_trace_id,
            "user_id": candidate.user_id,
            "agent_name": candidate.agent_name,
            "duration_ms": candidate.duration_ms,
            "cost_usd": candidate.cost_usd,
            "source_started_at": candidate.source_started_at,
            "extracted_at": candidate.extracted_at,
        }
    return list(rows.values()), dropped


def prepare_failures(
    project_id: str,
    config_sha: str,
    candidates: list[FailureSignatureCandidate],
) -> tuple[list[Row], Dropped]:
    cfg = failure_config()
    categories = set(cfg.extraction.taxonomy.labels())
    severities = set(cfg.extraction.severity.labels())
    dimensions = cfg.embedding.dimensions
    normalization = cfg.extraction.normalization_version
    max_evidence = cfg.extraction.max_evidence_spans
    dropped: Dropped = {}
    rows: dict[uuid.UUID, Row] = {}

    for candidate in candidates:
        signature = canonicalize_signature(
            candidate.signature, normalization_version=normalization
        )
        if not _accepts(signature, candidate.vector, dimensions, dropped):
            continue
        # Sorted and deduplicated so two identical failures compare equal during
        # reconciliation, with the onset a member so the row is attributable.
        turn_trace_ids = sorted(set(candidate.turn_trace_ids))
        if not turn_trace_ids or candidate.onset_turn_trace_id not in turn_trace_ids:
            _count(dropped, GATE_UNGROUNDED_ATTRIBUTION)
            continue
        row_id = signature_id(
            project_id,
            candidate.conversation_id,
            candidate.onset_turn_trace_id,
            signature,
            candidate.source_started_at,
        )
        _note_duplicate(rows, row_id, dropped)
        rows[row_id] = {
            "project_id": project_id,
            "id": row_id,
            "config_sha": config_sha,
            "signature": signature,
            "signature_display": candidate.signature.strip(),
            "failure_reason": candidate.failure_reason,
            "category": _label(
                candidate.category, categories, dropped, GATE_UNKNOWN_CATEGORY
            ),
            "severity": _optional_label(
                candidate.severity, severities, dropped, GATE_UNKNOWN_SEVERITY
            ),
            "vector": candidate.vector,
            "conversation_id": candidate.conversation_id,
            "onset_turn_trace_id": candidate.onset_turn_trace_id,
            "turn_trace_ids": turn_trace_ids,
            # Truncated rather than gated: the config declares the bound, and a
            # judge citing a fourth span is not a reason to lose the failure.
            "evidence_span_ids": candidate.evidence_span_ids[:max_evidence],
            "user_id": candidate.user_id,
            "agent_name": candidate.agent_name,
            "duration_ms": candidate.duration_ms,
            "cost_usd": candidate.cost_usd,
            "source_started_at": candidate.source_started_at,
            "extracted_at": candidate.extracted_at,
        }
    return list(rows.values()), dropped


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
    if not value or value in allowed:
        return value
    _count(dropped, gate)
    return ""


def _note_duplicate(
    rows: dict[uuid.UUID, Row], key: uuid.UUID, dropped: Dropped
) -> None:
    if key in rows:
        _count(dropped, GATE_DUPLICATE_IN_BATCH)


def _count(dropped: Dropped, gate: str) -> None:
    dropped[gate] = dropped.get(gate, 0) + 1
