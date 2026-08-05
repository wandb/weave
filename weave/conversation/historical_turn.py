"""Deterministic, idempotent ingest for completed historical agent turns.

Schema v1 in this vertical slice sends canonical JSON with HTTP identity
encoding. ``compressed_bytes`` is a deterministic gzip preview, not the wire
body size. Callers must inspect :func:`get_turn_capabilities` and may reject
this prototype when gzipped protobuf is required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypeAlias

from weave.conversation.conversation import (
    LLM,
    SubAgent,
    Tool,
    Turn,
    _attrs_for_span,
    _capture_info_attrs,
)
from weave.conversation.types import Message
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace_server.agents.historical_turn_validation import (
    HistoricalTurnCapabilityMismatchError,
    HistoricalTurnPayloadTooLargeError,
    HistoricalTurnValidationError,
    compute_historical_turn_child_span_id,
    compute_historical_turn_logical_key,
    compute_historical_turn_payload_sizes,
    compute_historical_turn_root_span_id,
    compute_historical_turn_trace_id,
    compute_historical_turn_wire_sha256,
    validate_prepared_turn,
)
from weave.trace_server.agents.types import (
    HistoricalTurnCapabilitiesReq,
    HistoricalTurnCapabilitiesRes,
    HistoricalTurnSpan,
    HistoricalTurnStatusReq,
    HistoricalTurnStatusRes,
    HistoricalTurnUpsertReq,
    HistoricalTurnUpsertRes,
    PreparedTurn,
)

HistoricalTurnCapabilities: TypeAlias = HistoricalTurnCapabilitiesRes
HistoricalTurnStatus: TypeAlias = HistoricalTurnStatusRes
HistoricalTurnUpsertResult: TypeAlias = HistoricalTurnUpsertRes

__all__ = [
    "HistoricalTurnCapabilities",
    "HistoricalTurnCapabilityMismatchError",
    "HistoricalTurnPayloadTooLargeError",
    "HistoricalTurnStatus",
    "HistoricalTurnUpsertResult",
    "HistoricalTurnValidationError",
    "PreparedTurn",
    "get_turn_capabilities",
    "get_turn_status",
    "prepare_turn",
    "upsert_turn",
]


def prepare_turn(
    *,
    conversation_id: str,
    turn_key: str,
    source_payload_sha256: str,
    agent_name: str = "",
    conversation_name: str = "",
    model: str = "",
    agent_id: str = "",
    agent_description: str = "",
    agent_version: str = "",
    messages: list[Message] | None = None,
    output_messages: list[Message] | None = None,
    system_instructions: list[str] | None = None,
    spans: list[LLM | Tool | SubAgent] | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    include_content: bool = True,
    continue_parent_trace: bool = False,
    attributes: dict[str, Any] | None = None,
) -> PreparedTurn:
    """Prepare one historical turn without writing anything.

    The regular ``log_turn`` fields are accepted, plus a stable source
    ``turn_key`` and the SHA-256 of the source payload. Every span must carry
    completed historical timestamps. The returned envelope has deterministic
    trace/span IDs and a canonical wire hash, and is safe to retry through
    :func:`upsert_turn`.

    This API never silently truncates. Payloads beyond the advertised local
    limit fail here before a network call; content externalization is not part
    of schema v1.
    """
    if continue_parent_trace:
        raise HistoricalTurnValidationError(
            "historical turns must be standalone traces; "
            "continue_parent_trace=True is not supported"
        )
    _validate_custom_attributes(attributes)

    root_start_ns = _required_timestamp_ns(started_at, "started_at")
    root_end_ns = _required_timestamp_ns(ended_at, "ended_at")
    if root_end_ns < root_start_ns:
        raise HistoricalTurnValidationError("ended_at must not precede started_at")

    project_id = require_weave_client().project_id
    logical_key = compute_historical_turn_logical_key(
        project_id, conversation_id, turn_key
    )
    trace_id = compute_historical_turn_trace_id(logical_key)
    root_span_id = compute_historical_turn_root_span_id(logical_key)

    resolved_spans = spans or []
    turn = Turn(
        agent_name=agent_name,
        model=model,
        agent_id=agent_id,
        agent_description=agent_description,
        agent_version=agent_version,
        system_instructions=system_instructions or [],
        messages=messages or [],
        output_messages=output_messages or [],
        spans=resolved_spans,
        started_at=started_at,
        ended_at=ended_at,
        continue_parent_trace=False,
    )
    root_attributes = _without_capture_info(
        turn._build_attrs(
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            include_content=include_content,
        )
    )
    if attributes:
        root_attributes.update(attributes)
    root_attributes.update(
        {
            "historical_turn.logical_key": logical_key,
            "historical_turn.turn_key": turn_key,
            "historical_turn.source_payload_sha256": source_payload_sha256,
            "historical_turn.schema_version": "1",
        }
    )

    prepared_spans = [
        HistoricalTurnSpan(
            kind="turn",
            name=f"invoke_agent {agent_name}",
            trace_id=trace_id,
            span_id=root_span_id,
            parent_span_id=None,
            start_time_unix_nano=root_start_ns,
            end_time_unix_nano=root_end_ns,
            attributes=root_attributes,
        )
    ]

    for index, child in enumerate(resolved_spans):
        child_start_ns = _required_timestamp_ns(
            child.started_at, f"spans[{index}].started_at"
        )
        child_end_ns = _required_timestamp_ns(
            child.ended_at, f"spans[{index}].ended_at"
        )
        name, child_attributes = _attrs_for_span(
            child,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            include_content=include_content,
        )
        child_attributes = _without_capture_info(child_attributes)
        if attributes:
            child_attributes.update(attributes)
        prepared_spans.append(
            HistoricalTurnSpan(
                kind=_span_kind(child),
                name=name,
                trace_id=trace_id,
                span_id=compute_historical_turn_child_span_id(
                    logical_key, index, _span_kind(child)
                ),
                parent_span_id=root_span_id,
                start_time_unix_nano=child_start_ns,
                end_time_unix_nano=child_end_ns,
                attributes=child_attributes,
            )
        )

    provisional = PreparedTurn(
        logical_key=logical_key,
        turn_key=turn_key,
        source_payload_sha256=source_payload_sha256,
        wire_sha256="0" * 64,
        compressed_bytes=0,
        uncompressed_bytes=0,
        reference_count=0,
        destination_project_id=project_id,
        conversation_id=conversation_id,
        trace_id=trace_id,
        root_span_id=root_span_id,
        spans=prepared_spans,
        span_count=len(prepared_spans),
    )
    compressed_bytes, uncompressed_bytes = compute_historical_turn_payload_sizes(
        provisional
    )
    sized = provisional.model_copy(
        update={
            "compressed_bytes": compressed_bytes,
            "uncompressed_bytes": uncompressed_bytes,
        }
    )
    prepared = sized.model_copy(
        update={"wire_sha256": compute_historical_turn_wire_sha256(sized)}
    )
    validate_prepared_turn(prepared, project_id=project_id)
    return prepared


def upsert_turn(prepared: PreparedTurn) -> HistoricalTurnUpsertResult:
    """Atomically commit a prepared turn or replay its prior result."""
    client = require_weave_client()
    validate_prepared_turn(prepared, project_id=client.project_id)
    result = client.server.historical_turn_upsert(
        HistoricalTurnUpsertReq(
            project_id=client.project_id,
            capability_version=prepared.capability_version,
            turn=prepared,
        )
    )
    _validate_upsert_evidence(result, prepared=prepared)
    return result


def get_turn_status(logical_key: str) -> HistoricalTurnStatus:
    """Read durable commit evidence for ``logical_key`` in the active project."""
    client = require_weave_client()
    result = client.server.historical_turn_status(
        HistoricalTurnStatusReq(
            project_id=client.project_id,
            logical_key=logical_key,
        )
    )
    _validate_status_evidence(result, requested_logical_key=logical_key)
    return result


def get_turn_capabilities() -> HistoricalTurnCapabilities:
    """Return the active project's historical-turn guarantees and hard limits."""
    client = require_weave_client()
    return client.server.historical_turn_capabilities(
        HistoricalTurnCapabilitiesReq(project_id=client.project_id)
    )


def _required_timestamp_ns(value: datetime | None, field_name: str) -> int:
    if value is None:
        raise HistoricalTurnValidationError(
            f"{field_name} is required for historical ingest"
        )
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalTurnValidationError(f"{field_name} must be timezone-aware")
    utc_value = value.astimezone(timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = utc_value - epoch
    if delta.days < 0:
        raise HistoricalTurnValidationError(f"{field_name} must be at or after 1970")
    return (
        delta.days * 86_400 + delta.seconds
    ) * 1_000_000_000 + delta.microseconds * 1_000


def _span_kind(span: LLM | Tool | SubAgent) -> str:
    if isinstance(span, LLM):
        return "llm"
    if isinstance(span, Tool):
        return "tool"
    if isinstance(span, SubAgent):
        return "subagent"
    raise HistoricalTurnValidationError(
        f"unsupported historical child span type: {type(span).__name__}"
    )


def _without_capture_info(attributes: dict[str, Any]) -> dict[str, Any]:
    stable = dict(attributes)
    for key in _capture_info_attrs():
        stable.pop(key, None)
    return stable


def _validate_custom_attributes(attributes: dict[str, Any] | None) -> None:
    for key in attributes or {}:
        if not isinstance(key, str):
            raise HistoricalTurnValidationError("attribute keys must be strings")
        if key.startswith(("gen_ai.", "weave.", "historical_turn.")):
            raise HistoricalTurnValidationError(
                f"historical ingest attribute {key!r} uses a reserved namespace"
            )


def _validate_status_evidence(
    result: HistoricalTurnStatus,
    *,
    requested_logical_key: str,
) -> None:
    if result.logical_key != requested_logical_key:
        raise RuntimeError("historical turn status returned a different logical_key")

    if result.status == "absent":
        has_commit_evidence = any(
            (
                result.wire_sha256 is not None,
                result.commit_id is not None,
                result.storage_row_key is not None,
                bool(result.trace_ids),
                bool(result.root_span_ids),
                result.span_count != 0,
                result.last_error is not None,
            )
        )
        if has_commit_evidence:
            raise RuntimeError("absent historical turn status returned commit evidence")
        return

    if not _is_lower_hex(result.wire_sha256, 64):
        raise RuntimeError("historical turn status returned an invalid wire_sha256")
    if not result.commit_id:
        raise RuntimeError("historical turn status returned an empty commit_id")
    expected_trace_id = compute_historical_turn_trace_id(requested_logical_key)
    expected_root_span_id = compute_historical_turn_root_span_id(requested_logical_key)
    if result.trace_ids != [expected_trace_id]:
        raise RuntimeError("historical turn status returned invalid trace_ids")
    if result.root_span_ids != [expected_root_span_id]:
        raise RuntimeError("historical turn status returned invalid root_span_ids")
    if result.span_count < 1:
        raise RuntimeError("historical turn status returned an invalid span_count")

    if result.status == "committed":
        if not result.storage_row_key:
            raise RuntimeError(
                "committed historical turn status returned an empty storage_row_key"
            )
        if result.last_error is not None:
            raise RuntimeError("committed historical turn status returned a last_error")
    elif result.storage_row_key is not None:
        raise RuntimeError(
            "committing historical turn status returned a storage_row_key"
        )


def _validate_upsert_evidence(
    result: HistoricalTurnUpsertResult,
    *,
    prepared: PreparedTurn,
) -> None:
    if result.logical_key != prepared.logical_key:
        raise RuntimeError("historical turn server returned a different logical_key")
    if result.wire_sha256 != prepared.wire_sha256:
        raise RuntimeError("historical turn server returned a different wire_sha256")

    if result.status == "conflict":
        if (
            not _is_lower_hex(result.existing_wire_sha256, 64)
            or result.existing_wire_sha256 == prepared.wire_sha256
        ):
            raise RuntimeError(
                "historical turn conflict returned an invalid existing_wire_sha256"
            )
        if (
            result.commit_id is not None
            or result.trace_ids
            or result.root_span_ids
            or result.span_count != 0
        ):
            raise RuntimeError(
                "historical turn conflict returned contradictory commit evidence"
            )
        return

    if (
        result.trace_ids != [prepared.trace_id]
        or result.root_span_ids != [prepared.root_span_id]
        or result.span_count != prepared.span_count
    ):
        raise RuntimeError(
            "historical turn server returned inconsistent commit evidence"
        )
    if not result.commit_id:
        raise RuntimeError("historical turn server returned an empty commit_id")
    if result.existing_wire_sha256 is not None:
        raise RuntimeError(
            "historical turn server returned an unexpected existing_wire_sha256"
        )

    if result.status in {"committed", "replayed"}:
        if not result.storage_row_key:
            raise RuntimeError(
                "committed historical turn response returned an empty storage_row_key"
            )
    elif result.storage_row_key is not None:
        raise RuntimeError(
            "committing historical turn response returned a storage_row_key"
        )


def _is_lower_hex(value: str | None, length: int) -> bool:
    return (
        value is not None
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )
