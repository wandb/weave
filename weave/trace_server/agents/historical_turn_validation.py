"""Deterministic hashing and validation for historical turn envelopes.

This module is intentionally shared by the Python SDK and trace server. A
prepared payload must hash to the same bytes on both sides of the HTTP
boundary; keeping the canonical encoder here avoids subtly different client
and server implementations.

This vertical slice uses canonical JSON with an identity-encoded HTTP body. It
does *not* implement the approved gzipped-protobuf transport yet. The
deterministic ``gzip(mtime=0)`` calculation is preview metadata only, and the
capabilities response advertises that distinction explicitly.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from typing import Any

from pydantic import ValidationError

from weave.trace_server.agents.types import PreparedTurn

HISTORICAL_TURN_SCHEMA_VERSION = "1"
HISTORICAL_TURN_CAPABILITY_VERSION = "historical-turn-v1"
MAX_HISTORICAL_TURN_ENVELOPE_BYTES = 16 * 1024 * 1024
MAX_HISTORICAL_TURN_SPANS = 512
MAX_HISTORICAL_TURN_LOGICAL_KEY_BYTES = 64
MAX_HISTORICAL_TURN_ATTRIBUTE_COUNT = 256
MAX_HISTORICAL_TURN_ATTRIBUTE_KEY_BYTES = 512


class HistoricalTurnValidationError(ValueError):
    """A historical turn is invalid and must not be written."""

    http_status_code = 422


class HistoricalTurnCapabilityMismatchError(HistoricalTurnValidationError):
    """The client and server historical-turn contracts differ."""

    http_status_code = 412


class HistoricalTurnPayloadTooLargeError(HistoricalTurnValidationError):
    """A historical turn exceeds the advertised atomic-envelope limit."""

    http_status_code = 413


def canonical_json_bytes(value: Any) -> bytes:
    """Return the one canonical JSON encoding used by historical turns."""
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HistoricalTurnValidationError(
            f"historical turn contains a non-canonical JSON value: {exc}"
        ) from exc


def historical_turn_hash_payload(turn: PreparedTurn) -> dict[str, Any]:
    """Return the model payload covered by ``wire_sha256``."""
    return turn.model_dump(mode="json", exclude={"wire_sha256"})


def compute_historical_turn_wire_sha256(turn: PreparedTurn) -> str:
    return hashlib.sha256(
        canonical_json_bytes(historical_turn_hash_payload(turn))
    ).hexdigest()


def compute_historical_turn_logical_key(
    project_id: str, conversation_id: str, turn_key: str
) -> str:
    """Hash the stable source identity in its destination-project domain."""
    return hashlib.sha256(
        b"hivemind-weave-turn-v1\0"
        + project_id.encode("utf-8")
        + b"\0"
        + conversation_id.encode("utf-8")
        + b"\0"
        + turn_key.encode("utf-8")
    ).hexdigest()


def compute_historical_turn_trace_id(logical_key: str) -> str:
    """Return the schema-v1 trace ID for a logical historical turn."""
    return _compute_historical_turn_id("trace", logical_key, 32)


def compute_historical_turn_root_span_id(logical_key: str) -> str:
    """Return the schema-v1 root span ID for a logical historical turn."""
    return _compute_historical_turn_id("root", logical_key, 16)


def compute_historical_turn_child_span_id(
    logical_key: str, child_index: int, span_kind: str
) -> str:
    """Return the schema-v1 span ID for one ordered direct child."""
    return _compute_historical_turn_id(
        f"child:{child_index}:{span_kind}", logical_key, 16
    )


def compute_historical_turn_payload_sizes(turn: PreparedTurn) -> tuple[int, int]:
    """Return deterministic ``(compressed, uncompressed)`` preview sizes."""
    payload = turn.model_dump(
        mode="json",
        exclude={
            "wire_sha256",
            "compressed_bytes",
            "uncompressed_bytes",
            "reference_count",
        },
    )
    wire = canonical_json_bytes(payload)
    compressed = gzip.compress(wire, compresslevel=9, mtime=0)
    return len(compressed), len(wire)


def historical_turn_wire_bytes(turn: PreparedTurn) -> int:
    """Measure the actual JSON model sent in an upsert request."""
    return len(canonical_json_bytes(turn.model_dump(mode="json")))


def validate_prepared_turn(turn: PreparedTurn, *, project_id: str | None = None) -> int:
    """Validate all bounded and wire-level invariants before any write.

    Returns the serialized envelope size for prepare responses and metrics.
    Pydantic validates tree shape, IDs, and timestamps. This function handles
    deterministic hashing, hard resource limits, and the narrower OTel
    attribute value domain.
    """
    try:
        PreparedTurn.model_validate(turn.model_dump(mode="python"))
    except ValidationError as exc:
        raise HistoricalTurnValidationError(
            f"historical turn envelope is structurally invalid: {exc}"
        ) from exc

    if turn.capability_version != HISTORICAL_TURN_CAPABILITY_VERSION:
        raise HistoricalTurnCapabilityMismatchError(
            "historical turn capability mismatch: expected "
            f"{HISTORICAL_TURN_CAPABILITY_VERSION!r}, got "
            f"{turn.capability_version!r}"
        )
    if turn.schema_version != HISTORICAL_TURN_SCHEMA_VERSION:
        raise HistoricalTurnValidationError(
            f"unsupported historical turn schema version {turn.schema_version!r}"
        )
    if turn.reference_count != 0:
        raise HistoricalTurnValidationError(
            "historical turn schema v1 does not support content references"
        )
    compressed_bytes, uncompressed_bytes = compute_historical_turn_payload_sizes(turn)
    if (
        turn.compressed_bytes != compressed_bytes
        or turn.uncompressed_bytes != uncompressed_bytes
    ):
        raise HistoricalTurnValidationError(
            "historical turn size metadata does not match its canonical payload"
        )
    if project_id is not None and turn.destination_project_id != project_id:
        raise HistoricalTurnValidationError(
            "historical turn destination project does not match the request project"
        )
    expected_logical_key = compute_historical_turn_logical_key(
        turn.destination_project_id, turn.conversation_id, turn.turn_key
    )
    if turn.logical_key != expected_logical_key:
        raise HistoricalTurnValidationError(
            "historical turn logical_key does not match its destination project "
            "and source identity"
        )
    expected_trace_id = compute_historical_turn_trace_id(turn.logical_key)
    expected_root_span_id = compute_historical_turn_root_span_id(turn.logical_key)
    if turn.trace_id != expected_trace_id:
        raise HistoricalTurnValidationError(
            "historical turn trace_id is not deterministic for its logical_key"
        )
    if turn.root_span_id != expected_root_span_id:
        raise HistoricalTurnValidationError(
            "historical turn root_span_id is not deterministic for its logical_key"
        )
    if len(turn.logical_key.encode("utf-8")) > MAX_HISTORICAL_TURN_LOGICAL_KEY_BYTES:
        raise HistoricalTurnValidationError("historical turn logical key is too large")
    if turn.span_count > MAX_HISTORICAL_TURN_SPANS:
        raise HistoricalTurnValidationError(
            f"historical turn has {turn.span_count} spans; maximum is "
            f"{MAX_HISTORICAL_TURN_SPANS}"
        )

    for index, span in enumerate(turn.spans):
        expected_span_id = (
            expected_root_span_id
            if index == 0
            else compute_historical_turn_child_span_id(
                turn.logical_key, index - 1, span.kind
            )
        )
        if span.span_id != expected_span_id:
            raise HistoricalTurnValidationError(
                f"spans[{index}] span_id is not deterministic for its logical_key"
            )
        if len(span.attributes) > MAX_HISTORICAL_TURN_ATTRIBUTE_COUNT:
            raise HistoricalTurnValidationError(
                f"spans[{index}] has {len(span.attributes)} attributes; maximum is "
                f"{MAX_HISTORICAL_TURN_ATTRIBUTE_COUNT}"
            )
        for key, value in span.attributes.items():
            if len(key.encode("utf-8")) > MAX_HISTORICAL_TURN_ATTRIBUTE_KEY_BYTES:
                raise HistoricalTurnValidationError(
                    f"spans[{index}] attribute key is too large: {key!r}"
                )
            _validate_attribute_value(value, f"spans[{index}].attributes[{key!r}]")

        expected_operation = {
            "turn": "invoke_agent",
            "llm": "chat",
            "tool": "execute_tool",
            "subagent": "invoke_agent",
        }[span.kind]
        if span.attributes.get("gen_ai.operation.name") != expected_operation:
            raise HistoricalTurnValidationError(
                f"spans[{index}] operation does not match kind {span.kind!r}"
            )
        if span.attributes.get("gen_ai.conversation.id") != turn.conversation_id:
            raise HistoricalTurnValidationError(
                f"spans[{index}] conversation ID does not match the envelope"
            )

    root_attributes = turn.spans[0].attributes
    expected_root_certificate = {
        "historical_turn.logical_key": turn.logical_key,
        "historical_turn.turn_key": turn.turn_key,
        "historical_turn.source_payload_sha256": turn.source_payload_sha256,
        "historical_turn.schema_version": turn.schema_version,
    }
    for key, expected_value in expected_root_certificate.items():
        if root_attributes.get(key) != expected_value:
            raise HistoricalTurnValidationError(
                f"turn root attribute {key!r} does not match the envelope"
            )

    actual_hash = compute_historical_turn_wire_sha256(turn)
    if actual_hash != turn.wire_sha256:
        raise HistoricalTurnValidationError(
            "historical turn wire_sha256 does not match its canonical payload"
        )

    wire_bytes = historical_turn_wire_bytes(turn)
    if wire_bytes > MAX_HISTORICAL_TURN_ENVELOPE_BYTES:
        raise HistoricalTurnPayloadTooLargeError(
            f"historical turn is {wire_bytes} bytes; maximum is "
            f"{MAX_HISTORICAL_TURN_ENVELOPE_BYTES}. This server does not yet "
            "support externalized historical-turn content; content was not truncated."
        )
    return wire_bytes


def _compute_historical_turn_id(domain: str, logical_key: str, hex_length: int) -> str:
    value = hashlib.sha256(
        b"weave-historical-turn-id-v1\0"
        + domain.encode("utf-8")
        + b"\0"
        + logical_key.encode("ascii")
    ).hexdigest()[:hex_length]
    if set(value) == {"0"}:
        return "0" * (hex_length - 1) + "1"
    return value


def _validate_attribute_value(value: Any, path: str) -> None:
    if isinstance(value, bool | str | int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise HistoricalTurnValidationError(f"{path} must be a finite float")
        return
    if not isinstance(value, list | tuple):
        raise HistoricalTurnValidationError(
            f"{path} must be an OTel scalar or homogeneous scalar sequence"
        )
    if not value:
        return

    first_type = type(value[0])
    if first_type not in {bool, str, int, float}:
        raise HistoricalTurnValidationError(
            f"{path} must contain only OTel scalar values"
        )
    for item in value:
        if type(item) is not first_type:
            raise HistoricalTurnValidationError(f"{path} must be homogeneous")
        if isinstance(item, float) and not math.isfinite(item):
            raise HistoricalTurnValidationError(f"{path} must contain finite floats")
