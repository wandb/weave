"""Validate and normalize signature candidates before insertion.

Malformed candidates are dropped and unknown labels are repaired. The server owns
identity: a row's `id` is derived from the fields that make the occurrence unique,
so a retried or replayed write collapses in the merge instead of double-counting.
"""

from __future__ import annotations

import unicodedata
import uuid
from collections import Counter

from weave.trace_server.errors import InvalidRequest
from weave.trace_server.insights import config
from weave.trace_server.insights.enums import InsightSignatureType, InsightWriteGate
from weave.trace_server.insights.write_types import (
    FailureSignatureCandidate,
    InsightSignatureCandidateBase,
    IntentSignatureCandidate,
)

FALLBACK_LABEL = "other"
UNKNOWN_LANGUAGE = "und"

# Namespace for the derived row id. Changing it re-mints every id and so orphans
# every stored row from its replays; it is permanent.
ROW_ID_NAMESPACE = uuid.UUID("320faf23-fcac-48f0-9161-54f2ab433304")

Row = dict[str, object]
GateCounts = Counter[InsightWriteGate]


def validate_config_sha(signature_type: InsightSignatureType, claimed: str) -> None:
    """Require the caller to agree with the deployed config.

    A row points at its config by digest, so a digest this deployment cannot
    resolve would be an unreadable provenance pointer.
    """
    actual = config.deployed_config_sha(signature_type)
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
    return collapsed.rstrip(" .").casefold()


def prepare_intents(
    project_id: str,
    config_sha: str,
    candidates: list[IntentSignatureCandidate],
) -> tuple[list[Row], GateCounts]:
    cfg = config.load_intent_config()
    categories = _label_names(cfg.extraction.taxonomy)
    sentiments = _label_names(cfg.extraction.sentiment)
    gate_counts: GateCounts = Counter()
    rows: dict[uuid.UUID, Row] = {}

    for candidate in candidates:
        signature = _gate(cfg, candidate, gate_counts)
        if signature is None:
            continue
        row_id = _row_id(
            project_id,
            config_sha,
            candidate.conversation_id,
            candidate.trace_id,
            signature,
        )
        row = {
            "id": row_id,
            **_base_row(project_id, config_sha, signature, candidate),
            "category": _label(
                candidate.category, categories, gate_counts, "unknown_category"
            ),
            "language": candidate.language or UNKNOWN_LANGUAGE,
            "sentiment": _optional_label(
                candidate.sentiment, sentiments, gate_counts, "unknown_sentiment"
            ),
            "sentiment_rationale": candidate.sentiment_rationale,
            "trace_id": candidate.trace_id,
        }
        _store(rows, row_id, row, gate_counts)
    return list(rows.values()), gate_counts


def prepare_failures(
    project_id: str,
    config_sha: str,
    candidates: list[FailureSignatureCandidate],
) -> tuple[list[Row], GateCounts]:
    cfg = config.load_failure_config()
    categories = _label_names(cfg.extraction.taxonomy)
    severities = _label_names(cfg.extraction.severity)
    gate_counts: GateCounts = Counter()
    rows: dict[uuid.UUID, Row] = {}

    for candidate in candidates:
        signature = _gate(cfg, candidate, gate_counts)
        if signature is None:
            continue
        affected = sorted(set(candidate.affected_trace_ids))
        if candidate.current_trace_id not in affected:
            gate_counts["ungrounded_attribution"] += 1
            continue
        row_id = _row_id(
            project_id,
            config_sha,
            candidate.conversation_id,
            candidate.current_trace_id,
            signature,
        )
        row = {
            "id": row_id,
            **_base_row(project_id, config_sha, signature, candidate),
            "failure_reason": candidate.failure_reason,
            "category": _label(
                candidate.category, categories, gate_counts, "unknown_category"
            ),
            "severity": _optional_label(
                candidate.severity, severities, gate_counts, "unknown_severity"
            ),
            "current_trace_id": candidate.current_trace_id,
            "affected_trace_ids": affected,
            "evidence_span_ids": sorted(set(candidate.evidence_span_ids)),
        }
        _store(rows, row_id, row, gate_counts)
    return list(rows.values()), gate_counts


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


def _store(
    rows: dict[uuid.UUID, Row], row_id: uuid.UUID, row: Row, gate_counts: GateCounts
) -> None:
    """File a row under its derived id, which is also its in-batch dedupe key."""
    if row_id in rows:
        gate_counts["duplicate_in_batch"] += 1
    rows[row_id] = row


def _row_id(
    project_id: str, config_sha: str, conversation_id: str, turn_id: str, signature: str
) -> uuid.UUID:
    """Identity of one judged occurrence: one signature, off one turn, under one config.

    Derived rather than minted, so a replay of the same batch reuses the id and the
    ReplacingMergeTree collapses the pair. A NUL separator cannot appear in any part.
    """
    parts = (project_id, config_sha, conversation_id, turn_id, signature)
    return uuid.uuid5(ROW_ID_NAMESPACE, "\x00".join(parts))


def _label_names(taxonomy: config.TaxonomyRef) -> set[str]:
    return {label.name for label in taxonomy.labels()}


def _gate(
    cfg: config.SignatureConfig,
    candidate: InsightSignatureCandidateBase,
    gate_counts: GateCounts,
) -> str | None:
    """The candidate's stored signature, or `None` when a gate discards it."""
    signature = canonicalize_signature(
        candidate.signature,
        normalization_version=cfg.extraction.normalization_version,
    )
    if not signature:
        gate_counts["empty_signature"] += 1
        return None
    if len(candidate.vector) != cfg.embedding.dimensions:
        gate_counts["vector_dimensions"] += 1
        return None
    return signature


def _label(
    value: str, allowed: set[str], gate_counts: GateCounts, gate: InsightWriteGate
) -> str:
    if value in allowed:
        return value
    gate_counts[gate] += 1
    return FALLBACK_LABEL


def _optional_label(
    value: str, allowed: set[str], gate_counts: GateCounts, gate: InsightWriteGate
) -> str:
    """Keep missing labels distinct from real labels such as neutral or info."""
    if not value or value in allowed:
        return value
    gate_counts[gate] += 1
    return ""
