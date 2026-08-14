"""Validate and normalize signature candidates before insertion.

Malformed candidates are dropped and unknown labels are repaired. IDs and
signature hashes stay server-owned so re-extractions append and hashes match
ClickHouse's `sipHash128` implementation.
"""

from __future__ import annotations

import unicodedata
from functools import cache

from weave.trace_server.errors import InvalidRequest
from weave.trace_server.insights import config
from weave.trace_server.insights.types import (
    FailureSignatureCandidate,
    InsightSignatureCandidateBase,
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
GateCounts = dict[str, int]
DedupeKey = tuple[str, str, str]


def validate_config_sha(signature_type: str, claimed: str) -> None:
    """Require the caller to agree with the deployed config.

    A row points at its config by digest, so a digest this deployment cannot
    resolve would be an unreadable provenance pointer.
    """
    actual = config.config_sha(_load(signature_type))
    if claimed != actual:
        raise InvalidRequest(
            f"{signature_type} config_sha {claimed!r} does not match the deployed "
            f"config {actual!r}"
        )


def canonicalize_signature(text: str, *, normalization_version: int) -> str:
    """The stored form, so `GROUP BY signature` groups identity.

    Versioned by the config's `normalization_version`, which lives inside
    `config_sha`, so changing it is a visible digest move.
    """
    if normalization_version != 1:
        raise RuntimeError(f"unsupported normalization_version {normalization_version}")
    collapsed = " ".join(unicodedata.normalize("NFKC", text).split())
    return collapsed.rstrip(".").strip().casefold()


def prepare_intents(
    project_id: str,
    config_sha: str,
    candidates: list[IntentSignatureCandidate],
) -> tuple[list[Row], GateCounts]:
    cfg = _intent_config()
    categories = _label_names(cfg.extraction.taxonomy)
    sentiments = _label_names(cfg.extraction.sentiment)
    gate_counts: GateCounts = {}
    rows: dict[DedupeKey, Row] = {}

    for candidate in candidates:
        signature = _prepare_signature(
            candidate,
            cfg.extraction.normalization_version,
            cfg.embedding.dimensions,
            gate_counts,
        )
        if signature is None:
            continue
        key = (candidate.conversation_id, candidate.trace_id, signature)
        row = {
            **_base_row(project_id, config_sha, signature, candidate),
            "category": _label(
                candidate.category, categories, gate_counts, GATE_UNKNOWN_CATEGORY
            ),
            "language": candidate.language or UNKNOWN_LANGUAGE,
            "sentiment": _optional_label(
                candidate.sentiment, sentiments, gate_counts, GATE_UNKNOWN_SENTIMENT
            ),
            "sentiment_rationale": candidate.sentiment_rationale,
            "trace_id": candidate.trace_id,
        }
        _store_row(rows, key, row, gate_counts)
    return list(rows.values()), gate_counts


def prepare_failures(
    project_id: str,
    config_sha: str,
    candidates: list[FailureSignatureCandidate],
) -> tuple[list[Row], GateCounts]:
    cfg = _failure_config()
    categories = _label_names(cfg.extraction.taxonomy)
    severities = _label_names(cfg.extraction.severity)
    gate_counts: GateCounts = {}
    rows: dict[DedupeKey, Row] = {}

    for candidate in candidates:
        signature = _prepare_signature(
            candidate,
            cfg.extraction.normalization_version,
            cfg.embedding.dimensions,
            gate_counts,
        )
        if signature is None:
            continue
        affected = sorted(set(candidate.affected_trace_ids))
        if candidate.current_trace_id not in affected:
            _increment(gate_counts, GATE_UNGROUNDED_ATTRIBUTION)
            continue
        key = (candidate.conversation_id, candidate.current_trace_id, signature)
        row = {
            **_base_row(project_id, config_sha, signature, candidate),
            "failure_reason": candidate.failure_reason,
            "category": _label(
                candidate.category, categories, gate_counts, GATE_UNKNOWN_CATEGORY
            ),
            "severity": _optional_label(
                candidate.severity, severities, gate_counts, GATE_UNKNOWN_SEVERITY
            ),
            "current_trace_id": candidate.current_trace_id,
            "affected_trace_ids": affected,
            "evidence_span_ids": sorted(set(candidate.evidence_span_ids)),
        }
        _store_row(rows, key, row, gate_counts)
    return list(rows.values()), gate_counts


@cache
def _load(signature_type: str) -> config.SignatureConfig:
    return config.load_config(signature_type)


def _intent_config() -> config.IntentConfig:
    cfg = _load("intent")
    if not isinstance(cfg, config.IntentConfig):
        raise TypeError("intent.yaml does not declare the intent type")
    return cfg


def _failure_config() -> config.FailureConfig:
    cfg = _load("failure")
    if not isinstance(cfg, config.FailureConfig):
        raise TypeError("failure.yaml does not declare the failure type")
    return cfg


def _base_row(
    project_id: str,
    config_sha: str,
    signature: str,
    candidate: InsightSignatureCandidateBase,
) -> Row:
    return {
        "project_id": project_id,
        "config_sha": config_sha,
        "signature": signature,
        "vector": candidate.vector,
        "conversation_id": candidate.conversation_id,
        "user_id": candidate.user_id,
        "agent_name": candidate.agent_name,
        "turn_duration_ms": candidate.turn_duration_ms,
        "turn_cost_usd": candidate.turn_cost_usd,
        "trace_started_at": candidate.trace_started_at,
        "extracted_at": candidate.extracted_at,
    }


def _label_names(taxonomy: config.TaxonomyRef) -> set[str]:
    return {label.name for label in taxonomy.labels()}


def _prepare_signature(
    candidate: InsightSignatureCandidateBase,
    normalization_version: int,
    dimensions: int,
    gate_counts: GateCounts,
) -> str | None:
    signature = canonicalize_signature(
        candidate.signature, normalization_version=normalization_version
    )
    if not signature:
        _increment(gate_counts, GATE_EMPTY_SIGNATURE)
        return None
    if len(candidate.vector) != dimensions:
        _increment(gate_counts, GATE_VECTOR_DIMENSIONS)
        return None
    return signature


def _label(value: str, allowed: set[str], gate_counts: GateCounts, gate: str) -> str:
    if value in allowed:
        return value
    _increment(gate_counts, gate)
    return FALLBACK_LABEL


def _optional_label(
    value: str, allowed: set[str], gate_counts: GateCounts, gate: str
) -> str:
    """Keep missing labels distinct from real labels such as neutral or info."""
    if not value or value in allowed:
        return value
    _increment(gate_counts, gate)
    return ""


def _store_row(
    rows: dict[DedupeKey, Row], key: DedupeKey, row: Row, gate_counts: GateCounts
) -> None:
    if key in rows:
        _increment(gate_counts, GATE_DUPLICATE_IN_BATCH)
    rows[key] = row


def _increment(gate_counts: GateCounts, gate: str) -> None:
    gate_counts[gate] = gate_counts.get(gate, 0) + 1
