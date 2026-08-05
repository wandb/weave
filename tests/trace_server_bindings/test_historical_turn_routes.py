from __future__ import annotations

import hashlib
import json
from unittest.mock import patch

import httpx
import pytest

from weave.trace_server.agents.historical_turn_validation import (
    HistoricalTurnCapabilityMismatchError,
    HistoricalTurnPayloadTooLargeError,
    HistoricalTurnValidationError,
    compute_historical_turn_logical_key,
    compute_historical_turn_payload_sizes,
    compute_historical_turn_root_span_id,
    compute_historical_turn_trace_id,
    compute_historical_turn_wire_sha256,
)
from weave.trace_server.agents.types import (
    HistoricalTurnCapabilitiesReq,
    HistoricalTurnSpan,
    HistoricalTurnStatusReq,
    HistoricalTurnUpsertReq,
    PreparedTurn,
)
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)

PROJECT_ID = "entity/project"


def _prepared_turn() -> PreparedTurn:
    logical_key = compute_historical_turn_logical_key(PROJECT_ID, "conv", "turn")
    source_payload_sha256 = hashlib.sha256(b"source").hexdigest()
    trace_id = compute_historical_turn_trace_id(logical_key)
    root_span_id = compute_historical_turn_root_span_id(logical_key)
    provisional = PreparedTurn(
        logical_key=logical_key,
        turn_key="turn",
        source_payload_sha256=source_payload_sha256,
        wire_sha256="0" * 64,
        compressed_bytes=0,
        uncompressed_bytes=0,
        destination_project_id=PROJECT_ID,
        conversation_id="conv",
        trace_id=trace_id,
        root_span_id=root_span_id,
        spans=[
            HistoricalTurnSpan(
                kind="turn",
                name="invoke_agent codex",
                trace_id=trace_id,
                span_id=root_span_id,
                start_time_unix_nano=1,
                end_time_unix_nano=2,
                attributes={
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.conversation.id": "conv",
                    "historical_turn.logical_key": logical_key,
                    "historical_turn.turn_key": "turn",
                    "historical_turn.source_payload_sha256": source_payload_sha256,
                    "historical_turn.schema_version": "1",
                },
            )
        ],
        span_count=1,
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
    return sized.model_copy(
        update={"wire_sha256": compute_historical_turn_wire_sha256(sized)}
    )


def _response(body: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=body,
        request=httpx.Request("PUT", "http://example.com/historical-turn"),
    )


@pytest.mark.parametrize(
    ("method", "http_method", "req", "path", "response"),
    [
        (
            "historical_turn_upsert",
            "put",
            HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=_prepared_turn()),
            f"/agents/v1/historical-turns/{_prepared_turn().logical_key}",
            {
                "logical_key": _prepared_turn().logical_key,
                "wire_sha256": _prepared_turn().wire_sha256,
                "status": "committed",
                "commit_id": "commit",
                "storage_row_key": "row",
                "trace_ids": [_prepared_turn().trace_id],
                "root_span_ids": [_prepared_turn().root_span_id],
                "span_count": 1,
            },
        ),
        (
            "historical_turn_status",
            "get",
            HistoricalTurnStatusReq(
                project_id=PROJECT_ID, logical_key=_prepared_turn().logical_key
            ),
            f"/agents/v1/historical-turns/{_prepared_turn().logical_key}",
            {
                "logical_key": _prepared_turn().logical_key,
                "status": "absent",
            },
        ),
        (
            "historical_turn_capabilities",
            "get",
            HistoricalTurnCapabilitiesReq(project_id=PROJECT_ID),
            "/agents/v1/historical-turns/capabilities",
            {
                "supported": True,
                "capability_version": "historical-turn-v1",
                "transport_encoding": "canonical-json",
                "content_encoding": "identity",
                "preview_compression": "gzip-mtime-0",
                "schema_versions": ["1"],
                "max_envelope_bytes": 16 * 1024 * 1024,
                "max_spans": 512,
                "max_logical_key_bytes": 64,
                "atomic_turn_commit": True,
                "durable_idempotency": True,
                "status_lookup": True,
                "content_refs": "unsupported",
                "recovery_lease_seconds": 30,
            },
        ),
    ],
    ids=["upsert", "status", "capabilities"],
)
def test_historical_turn_routes_use_public_method_path_and_typed_payload(
    method: str,
    http_method: str,
    req,
    path: str,
    response: dict,
) -> None:
    server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
    response_status_code = 201 if method == "historical_turn_upsert" else 200
    with patch.object(
        server,
        http_method,
        return_value=_response(response, response_status_code),
    ) as mock_request:
        result = getattr(server, method)(req)

    mock_request.assert_called_once()
    assert mock_request.call_args.args[0] == path
    if http_method == "put":
        assert json.loads(mock_request.call_args.kwargs["data"]) == req.model_dump(
            mode="json", by_alias=True
        )
    else:
        assert mock_request.call_args.kwargs["params"] == {"project_id": PROJECT_ID}
    assert result.model_dump(mode="json", exclude_unset=True) == response


@pytest.mark.parametrize(
    ("status_code", "response_status"),
    [
        (200, "replayed"),
        (201, "committed"),
        (202, "committing"),
        (409, "conflict"),
    ],
)
def test_historical_turn_upsert_preserves_http_commit_semantics(
    status_code: int, response_status: str
) -> None:
    turn = _prepared_turn()
    req = HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)
    if response_status == "conflict":
        response_body = {
            "logical_key": turn.logical_key,
            "wire_sha256": turn.wire_sha256,
            "status": response_status,
            "storage_row_key": "existing-row",
            "existing_wire_sha256": "f" * 64,
        }
    else:
        response_body = {
            "logical_key": turn.logical_key,
            "wire_sha256": turn.wire_sha256,
            "status": response_status,
            "commit_id": "commit",
            "storage_row_key": (None if response_status == "committing" else "row"),
            "trace_ids": [turn.trace_id],
            "root_span_ids": [turn.root_span_id],
            "span_count": turn.span_count,
        }
    server = RemoteHTTPTraceServer("http://example.com", should_batch=False)

    with patch.object(
        server,
        "put",
        return_value=_response(response_body, status_code),
    ) as mock_put:
        result = server.historical_turn_upsert(req)

    mock_put.assert_called_once()
    assert result.model_dump(mode="json", exclude_unset=True) == response_body


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (412, HistoricalTurnCapabilityMismatchError),
        (413, HistoricalTurnPayloadTooLargeError),
        (422, HistoricalTurnValidationError),
    ],
)
def test_historical_turn_upsert_maps_typed_terminal_http_errors(
    status_code: int,
    error_type: type[HistoricalTurnValidationError],
) -> None:
    turn = _prepared_turn()
    req = HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)
    server = RemoteHTTPTraceServer("http://example.com", should_batch=False)

    with (
        patch.object(
            server,
            "put",
            return_value=_response({"reason": "content suppressed"}, status_code),
        ) as mock_put,
        pytest.raises(error_type) as exc_info,
    ):
        server.historical_turn_upsert(req)

    mock_put.assert_called_once()
    assert exc_info.value.http_status_code == status_code


def test_historical_turn_upsert_rejects_http_body_status_disagreement() -> None:
    turn = _prepared_turn()
    req = HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)
    response_body = {
        "logical_key": turn.logical_key,
        "wire_sha256": turn.wire_sha256,
        "status": "replayed",
        "commit_id": "commit",
        "storage_row_key": "row",
        "trace_ids": [turn.trace_id],
        "root_span_ids": [turn.root_span_id],
        "span_count": turn.span_count,
    }
    server = RemoteHTTPTraceServer("http://example.com", should_batch=False)

    with (
        patch.object(server, "put", return_value=_response(response_body, 201)),
        pytest.raises(
            RuntimeError,
            match="historical turn HTTP status disagrees with its response status",
        ),
    ):
        server.historical_turn_upsert(req)


def test_historical_turn_put_retries_transport_failure_with_identical_body() -> None:
    turn = _prepared_turn()
    req = HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)
    response_body = {
        "logical_key": turn.logical_key,
        "wire_sha256": turn.wire_sha256,
        "status": "committed",
        "commit_id": "commit",
        "storage_row_key": "row",
        "trace_ids": [turn.trace_id],
        "root_span_ids": [turn.root_span_id],
        "span_count": turn.span_count,
    }
    server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
    request = httpx.Request("PUT", "http://example.com/historical-turn")
    with (
        patch.object(
            server,
            "put",
            side_effect=[
                httpx.ConnectError("connection reset", request=request),
                _response(response_body, 201),
            ],
        ) as mock_put,
        patch("weave.utils.retry.retry_max_attempts", return_value=2),
        patch("weave.utils.retry.tenacity.wait_exponential_jitter") as mock_wait,
    ):
        mock_wait.return_value = lambda retry_state: 0
        result = server.historical_turn_upsert(req)

    assert mock_put.call_count == 2
    assert mock_put.call_args_list[0] == mock_put.call_args_list[1]
    assert json.loads(mock_put.call_args_list[0].kwargs["data"]) == req.model_dump(
        mode="json", by_alias=True
    )
    assert result.model_dump(mode="json", exclude_unset=True) == response_body
