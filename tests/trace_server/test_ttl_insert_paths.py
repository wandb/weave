"""Verify stored expiry for call and agent ingestion against ClickHouse."""

from __future__ import annotations

import asyncio
import datetime
import json
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.types import GenAIOTelExportReq
from weave.trace_server.async_clickhouse_trace_server import AsyncClickHouseTraceServer
from weave.trace_server.ch_sentinel_values import EXPIRE_AT_NEVER
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.opentelemetry.python_spans import Span as PythonSpan
from weave.trace_server.project_version.types import CallsStorageServerMode
from weave.trace_server.ttl_settings import reset_ttl_cache

TEST_ENTITY = "ttl_entity"
NANOSECONDS_PER_SECOND = 1_000_000_000
COMPLETION_RETENTION_DAYS = 30

# Raw-read targets for the v1 and v2 insert paths.
V1_READ_TABLE = "call_parts"
V2_READ_TABLE = "calls_complete"

# Retention policy → expected timedelta applied to the anchor.
# 0 sentinel is handled separately (far-future 2100-01-01).
RETENTION_CASES: list[tuple[int, datetime.timedelta | None]] = [
    (30, datetime.timedelta(days=30)),
    (0, None),
    (-5, datetime.timedelta(minutes=5)),
]
MESSAGE_TEXT_BY_ROLE = {
    "assistant": "A response",
    "system": "An instruction",
    "tool_call": "An argument",
    "tool_result": "A result",
    "user": "A question",
}


@pytest.fixture(params=["UTC", "America/Los_Angeles", "Asia/Kathmandu"])
def local_timezone(request, monkeypatch):
    try:
        with monkeypatch.context() as patch:
            patch.setenv("TZ", request.param)
            time.tzset()
            yield
    finally:
        time.tzset()


@pytest.fixture(autouse=True)
def _clear_ttl_cache():
    reset_ttl_cache()
    yield
    reset_ttl_cache()


@pytest.fixture
def internal_server(trace_server):
    server = trace_server._internal_trace_server
    assert isinstance(server, ClickHouseTraceServer)
    server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return server


def _set_retention_days(
    server: ClickHouseTraceServer,
    internal_project_id: str,
    retention_days: int,
) -> None:
    """Persist a retention_days row for the project in the backend."""
    server.ch_client.insert(
        "project_ttl_settings",
        [[internal_project_id, retention_days]],
        column_names=["project_id", "retention_days"],
    )


def _read_expire_at(
    server: ClickHouseTraceServer,
    internal_project_id: str,
    call_id: str,
    table: str,
) -> list[datetime.datetime]:
    """Raw-read expire_at value(s) for a call.

    `table` selects the CH table (`call_parts`, `calls_merged`, `calls_complete`).
    Returns a list so v1 call_parts (which stores one row per start/end) can
    return multiple rows; calls_complete always returns a single entry.
    """
    result = server.ch_client.query(
        f"SELECT expire_at FROM {table} "
        "WHERE project_id = {project_id:String} AND id = {call_id:String} "
        "ORDER BY expire_at",
        parameters={"project_id": internal_project_id, "call_id": call_id},
    )
    return [row[0] for row in result.result_rows]


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    """Tag naive datetimes as UTC without shifting wall-clock; normalize aware to UTC.

    expire_at is stored as UTC but the CH driver returns naive datetimes.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _assert_expire_at_matches(
    actual: list[datetime.datetime],
    anchor: datetime.datetime,
    retention_days: int,
    expected_delta: datetime.timedelta | None,
) -> None:
    """Assert every expire_at row equals anchor+delta (or sentinel when retention=0)."""
    assert actual, "expected at least one expire_at row from the raw read"
    expected = EXPIRE_AT_NEVER if expected_delta is None else anchor + expected_delta
    expected_utc = _as_utc(expected)
    for value in actual:
        assert _as_utc(value) == expected_utc, (
            f"retention_days={retention_days}: expected {expected_utc}, got {value!r}"
        )


def _make_project(suffix: str) -> tuple[str, str]:
    """Return (external_project_id, internal_project_id) for an isolated test project."""
    external = f"{TEST_ENTITY}/ttl_{suffix}_{uuid.uuid4().hex[:8]}"
    return external, b64(external)


def _now_utc() -> datetime.datetime:
    # Millisecond precision so CH round-trip comparisons line up exactly.
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


@pytest.mark.parametrize(
    ("retention_days", "expected_delta"), [*RETENTION_CASES, (None, None)]
)
@pytest.mark.parametrize("target", ["spans", "calls_complete", "calls_merged"])
@pytest.mark.parametrize(
    "anchor", [None, "2027-03-14T09:30:00+00:00", "2027-11-07T08:30:00+00:00"]
)
@pytest.mark.usefixtures("local_timezone")
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_otel_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta, target, anchor
):
    """OTel calls, spans, and copied messages expire at the original UTC instant."""
    external_project_id, internal_project_id = _make_project("agent_otel")
    if retention_days is not None:
        _set_retention_days(internal_server, internal_project_id, retention_days)

    started_at = _now_utc() - datetime.timedelta(minutes=1)
    if anchor is not None:
        started_at = datetime.datetime.fromisoformat(anchor)
    started_at = started_at.replace(microsecond=123000)

    expected_rows = []
    expected_messages = []
    spans = []
    trace_id = uuid.uuid4().bytes

    for offset in (0, 3600):
        span_id = uuid.uuid4().bytes[:8]
        span_start = started_at + datetime.timedelta(seconds=offset)
        start_ns = (
            int(span_start.timestamp()) * NANOSECONDS_PER_SECOND
            + span_start.microsecond * 1000
        )
        spans.append(
            Span(
                trace_id=trace_id,
                span_id=span_id,
                name="agent-turn",
                start_time_unix_nano=start_ns,
                end_time_unix_nano=start_ns + NANOSECONDS_PER_SECOND,
                attributes=[
                    KeyValue(key=key, value=AnyValue(string_value=value))
                    for key, value in {
                        "gen_ai.input.messages": json.dumps(
                            [{"role": "user", "content": MESSAGE_TEXT_BY_ROLE["user"]}]
                        ),
                        "gen_ai.output.messages": json.dumps(
                            [
                                {
                                    "role": "assistant",
                                    "content": MESSAGE_TEXT_BY_ROLE["assistant"],
                                }
                            ]
                        ),
                        "gen_ai.system_instructions": json.dumps(
                            [
                                {
                                    "type": "text",
                                    "content": MESSAGE_TEXT_BY_ROLE["system"],
                                }
                            ]
                        ),
                        "weave.tool.call.arguments": MESSAGE_TEXT_BY_ROLE["tool_call"],
                        "weave.tool.call.result": MESSAGE_TEXT_BY_ROLE["tool_result"],
                    }.items()
                ],
            )
        )
        parsed = PythonSpan.from_proto(spans[-1])
        start_call, end_call = parsed.to_call(external_project_id)
        assert start_call.started_at == span_start
        assert end_call.ended_at == span_start + datetime.timedelta(seconds=1)
        assert (
            start_call.otel_dump["start_time"]
            == datetime.datetime.fromtimestamp(span_start.timestamp()).isoformat()
        )
        assert (
            start_call.otel_dump["end_time"]
            == datetime.datetime.fromtimestamp(span_start.timestamp() + 1).isoformat()
        )

        expiry = (
            EXPIRE_AT_NEVER
            if expected_delta is None
            else span_start.replace(microsecond=0) + expected_delta
        )
        if target == "calls_merged" and expected_delta is not None:
            expiry = span_start + expected_delta
        expected_rows.append(
            (span_start, span_start + datetime.timedelta(seconds=1), expiry)
        )
        for role, content in MESSAGE_TEXT_BY_ROLE.items():
            expected_messages.append((span_start, role, content, expiry))

    entity, project = external_project_id.split("/")
    processed_spans = [
        tsi.ProcessedResourceSpans(
            entity=entity,
            project=project,
            run_id=None,
            resource_spans=ResourceSpans(scope_spans=[ScopeSpans(spans=spans)]),
        )
    ]
    if target == "spans":
        response = trace_server.genai_otel_export(
            GenAIOTelExportReq(
                project_id=external_project_id, processed_spans=processed_spans
            )
        )
        assert response.accepted_spans == len(spans)
        assert response.rejected_spans == 0
        assert response.error_message == ""
    elif target in {"calls_complete", "calls_merged"}:
        if target == "calls_merged":
            internal_server.table_routing_resolver._mode = (
                CallsStorageServerMode.FORCE_LEGACY
            )
        response = trace_server.otel_export(
            tsi.OTelExportReq(
                project_id=external_project_id,
                processed_spans=processed_spans,
                wb_user_id="test_user",
            )
        )
        assert response.partial_success is None
    else:
        raise AssertionError(f"Unexpected OTel target: {target}")

    result = internal_server.ch_client.query(
        "SELECT started_at, ended_at, expire_at FROM {target:Identifier} FINAL "
        "WHERE project_id = {project_id:String} ORDER BY started_at",
        parameters={"project_id": internal_project_id, "target": target},
    )
    actual_rows = [
        (_as_utc(start), _as_utc(end), _as_utc(expiry))
        for start, end, expiry in result.result_rows
    ]
    assert actual_rows == expected_rows

    if target == "spans":
        messages = internal_server.ch_client.query(
            "SELECT started_at, role, content, expire_at FROM messages "
            "WHERE project_id = {project_id:String} ORDER BY started_at, role",
            parameters={"project_id": internal_project_id},
        )
        actual_messages = [
            (_as_utc(start), role, content, _as_utc(expiry))
            for start, role, content, expiry in messages.result_rows
        ]
        assert actual_messages == expected_messages


@pytest.mark.parametrize("mode", ["sync", "stream", "async", "deferred"])
@pytest.mark.usefixtures("local_timezone")
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: stored span expiry"
)
def test_ttl_completion_uses_utc(trace_server, internal_server, monkeypatch, mode):
    """Tracked completions and their messages expire relative to the actual UTC start."""
    external_project_id, internal_project_id = _make_project("completion")
    _set_retention_days(internal_server, internal_project_id, COMPLETION_RETENTION_DAYS)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    request = tsi.CompletionsCreateReq(
        project_id=external_project_id,
        inputs=tsi.CompletionsCreateRequestInputs(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "A question"}],
        ),
        track_llm_call=True,
    )
    earliest_start = _now_utc()
    with (
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion",
            return_value=tsi.CompletionsCreateRes(
                response={
                    "choices": [
                        {"message": {"role": "assistant", "content": "A response"}}
                    ],
                }
            ),
        ),
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream",
            return_value=iter(
                [
                    {
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": "A response"},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                ]
            ),
        ),
    ):
        if mode == "stream":
            list(trace_server.completions_create_stream(request))
        elif mode == "sync":
            trace_server.completions_create(request)
        elif mode in {"async", "deferred"}:
            server = AsyncClickHouseTraceServer(
                host=internal_server._host,
                port=internal_server._port,
                database=internal_server._database,
            )
            request.project_id = internal_project_id
            request.wb_user_id = "test_user"
            asyncio.run(
                _run_async_completion(server, request, deferred=mode == "deferred")
            )
        else:
            raise AssertionError(f"Unexpected completion mode: {mode}")

    latest_end = datetime.datetime.now(datetime.timezone.utc)
    spans = internal_server.ch_client.query(
        "SELECT started_at, ended_at, expire_at FROM spans FINAL "
        "WHERE project_id = {project_id:String}",
        parameters={"project_id": internal_project_id},
    ).result_rows
    assert len(spans) == 1
    started_at, ended_at, expire_at = map(_as_utc, spans[0])
    assert earliest_start <= started_at <= ended_at <= latest_end
    assert expire_at == started_at.replace(microsecond=0) + datetime.timedelta(
        days=COMPLETION_RETENTION_DAYS
    )
    messages = internal_server.ch_client.query(
        "SELECT DISTINCT role, content, expire_at FROM messages "
        "WHERE project_id = {project_id:String} ORDER BY role",
        parameters={"project_id": internal_project_id},
    ).result_rows
    assert [(role, content, _as_utc(expiry)) for role, content, expiry in messages] == [
        ("assistant", "A response", expire_at),
        ("user", "A question", expire_at),
    ]


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_call_start_end_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """call_start + call_end: expire_at populated on v1 insert paths.

    Asserts on the two call_parts rows (start and end).
    """
    external_project_id, internal_project_id = _make_project("start_end")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    trace_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=external_project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )
    trace_server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=external_project_id,
                id=call_id,
                ended_at=ended_at,
                output={},
                summary={},
            )
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, V1_READ_TABLE
    )
    # Two rows: start (anchor=started_at) and end (anchor=ended_at).
    assert len(values) == 2
    _assert_expire_at_matches([values[0]], started_at, retention_days, expected_delta)
    _assert_expire_at_matches([values[1]], ended_at, retention_days, expected_delta)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_call_start_batch_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """call_start_batch: batched start/end items both populate expire_at.

    The external adapter does not wrap call_start_batch, so we hit the internal
    server directly with pre-encoded project ids.
    """
    _, internal_project_id = _make_project("batch")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    internal_server.call_start_batch(
        tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=internal_project_id,
                            id=call_id,
                            trace_id=trace_id,
                            op_name="op",
                            started_at=started_at,
                            attributes={},
                            inputs={},
                        )
                    ),
                ),
                tsi.CallBatchEndMode(
                    req=tsi.CallEndReq(
                        end=tsi.EndedCallSchemaForInsert(
                            project_id=internal_project_id,
                            id=call_id,
                            ended_at=ended_at,
                            output={},
                            summary={},
                        )
                    ),
                ),
            ]
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, V1_READ_TABLE
    )
    assert len(values) == 2
    _assert_expire_at_matches([values[0]], started_at, retention_days, expected_delta)
    _assert_expire_at_matches([values[1]], ended_at, retention_days, expected_delta)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_calls_complete_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """calls_complete: single-row v2 insert populates expire_at from started_at."""
    external_project_id, internal_project_id = _make_project("complete")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    trace_server.calls_complete(
        tsi.CallsUpsertCompleteReq(
            batch=[
                tsi.CompletedCallSchemaForInsert(
                    project_id=external_project_id,
                    id=call_id,
                    trace_id=trace_id,
                    op_name="op",
                    started_at=started_at,
                    ended_at=ended_at,
                    attributes={},
                    inputs={},
                    output=None,
                    summary={"usage": {}, "status_counts": {}},
                )
            ]
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, V2_READ_TABLE
    )
    assert len(values) == 1
    _assert_expire_at_matches(values, started_at, retention_days, expected_delta)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_call_start_v2_end_v2_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """call_start_v2 + call_end_v2: start seeds expire_at; end UPDATE leaves it intact."""
    external_project_id, internal_project_id = _make_project("v2")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    trace_server.call_start_v2(
        tsi.CallStartV2Req(
            start=tsi.StartedCallSchemaForInsert(
                project_id=external_project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )
    trace_server.call_end_v2(
        tsi.CallEndV2Req(
            end=tsi.EndedCallSchemaForInsertWithStartedAt(
                project_id=external_project_id,
                id=call_id,
                started_at=started_at,
                ended_at=ended_at,
                output={},
                summary={"usage": {}, "status_counts": {}},
            )
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, V2_READ_TABLE
    )
    assert len(values) == 1
    _assert_expire_at_matches(values, started_at, retention_days, expected_delta)


def test_project_ttl_settings_endpoints_round_trip(trace_server):
    """project_ttl_settings_read/update: default -> set -> clear, plus validation.

    Goes through the external adapter so this exercises both the adapter
    project/user-id translation and the backend implementation for whichever
    trace-server backend the test session is configured for.
    """
    external_project_id, _ = _make_project("settings_endpoints")
    read_req = tsi.ProjectTTLSettingsReadReq(project_id=external_project_id)

    # Unset project: read returns retention_days=None (no row).
    assert trace_server.project_ttl_settings_read(read_req).retention_days is None

    # Update to 30 days: response echoes value, subsequent read sees it.
    update_30 = trace_server.project_ttl_settings_update(
        tsi.ProjectTTLSettingsUpdateReq(
            project_id=external_project_id,
            retention_days=30,
            wb_user_id="ttl-user",
        )
    )
    assert update_30.retention_days == 30
    # Reusing read_req must not double-encode project_id (adapter copies req).
    assert trace_server.project_ttl_settings_read(read_req).retention_days == 30

    # Update to None: clears retention; subsequent read returns None again.
    update_none = trace_server.project_ttl_settings_update(
        tsi.ProjectTTLSettingsUpdateReq(
            project_id=external_project_id,
            retention_days=None,
            wb_user_id="ttl-user",
        )
    )
    assert update_none.retention_days is None
    assert trace_server.project_ttl_settings_read(read_req).retention_days is None

    # retention_days < 1 (other than None) is rejected.
    with pytest.raises(InvalidRequest):
        trace_server.project_ttl_settings_update(
            tsi.ProjectTTLSettingsUpdateReq(
                project_id=external_project_id,
                retention_days=0,
                wb_user_id="ttl-user",
            )
        )

    # wb_user_id is required for the audit trail.
    with pytest.raises(InvalidRequest):
        trace_server.project_ttl_settings_update(
            tsi.ProjectTTLSettingsUpdateReq(
                project_id=external_project_id,
                retention_days=30,
                wb_user_id=None,
            )
        )


async def _run_async_completion(server, request, *, deferred):
    with patch(
        "weave.trace_server.async_clickhouse_trace_server.lite_llm_acompletion",
        new=AsyncMock(
            return_value=tsi.CompletionsCreateRes(
                response={
                    "choices": [
                        {"message": {"role": "assistant", "content": "A response"}}
                    ]
                }
            )
        ),
    ):
        if deferred:
            result = await server.acompletions_create_deferred(request)
            assert result.span is not None
            await server.ainsert_completion_spans([result.span])
        else:
            await server.acompletions_create(request)
