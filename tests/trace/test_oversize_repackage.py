from __future__ import annotations

import datetime

import httpx
import pytest

from weave.trace.context import weave_client_context
from weave.trace.oversize_repackage import (
    OVERFLOW_BUNDLE_KEY,
    OVERSIZE_SUBTREE_BYTES,
    _walk_and_repackage,
    emit_user_warning,
    is_payload_too_large_error,
    repackage_call_fields,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallStartReq,
    CompletedCallSchemaForInsert,
    EndedCallSchemaForInsert,
    EndedCallSchemaForInsertWithStartedAt,
    StartedCallSchemaForInsert,
)
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
    _try_repackage_call_item,
)

BIG_BLOB = "x" * (OVERSIZE_SUBTREE_BYTES * 2)


def _make_http_error(status: int) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(
        f"status {status}",
        request=httpx.Request("POST", "http://x"),
        response=httpx.Response(status),
    )


def _start_item(*, inputs=None, attributes=None) -> StartBatchItem:
    start = StartedCallSchemaForInsert(
        project_id="ent/proj",
        id="0199_start_id",
        trace_id="0199_trace_id",
        op_name="op_name",
        started_at=datetime.datetime(2026, 5, 1),
        attributes=attributes or {},
        inputs=inputs or {},
    )
    return StartBatchItem(req=CallStartReq(start=start))


def _end_item(*, output=None, summary=None) -> EndBatchItem:
    end = EndedCallSchemaForInsert(
        project_id="ent/proj",
        id="0199_end_id",
        ended_at=datetime.datetime(2026, 5, 1),
        output=output,
        summary=summary or {},
    )
    return EndBatchItem(req=CallEndReq(end=end))


def _complete_item(
    *, inputs=None, attributes=None, output=None, summary=None
) -> CompleteBatchItem:
    req = CompletedCallSchemaForInsert(
        project_id="ent/proj",
        id="0199_complete_id",
        trace_id="0199_trace_id",
        op_name="op_name",
        started_at=datetime.datetime(2026, 5, 1),
        ended_at=datetime.datetime(2026, 5, 1, 0, 0, 1),
        attributes=attributes or {},
        inputs=inputs or {},
        output=output,
        summary=summary or {},
    )
    return CompleteBatchItem(req=req)


def _end_req_with_started_at(*, output=None, summary=None) -> CallEndReq:
    return CallEndReq(
        end=EndedCallSchemaForInsertWithStartedAt(
            project_id="ent/proj",
            id="0199_end_id",
            started_at=datetime.datetime(2026, 5, 1),
            ended_at=datetime.datetime(2026, 5, 1, 0, 0, 1),
            output=output,
            summary=summary or {},
        )
    )


def test_413_detection_only_matches_payload_too_large() -> None:
    assert is_payload_too_large_error(_make_http_error(413)) is True
    for status in (400, 404, 500):
        assert is_payload_too_large_error(_make_http_error(status)) is False
    assert is_payload_too_large_error(ValueError("not an http error")) is False


def test_emit_user_warning_silent_when_empty_names_paths_otherwise(caplog) -> None:
    with caplog.at_level("WARNING"):
        emit_user_warning([])
    assert all("repackaged" not in r.message for r in caplog.records)

    caplog.clear()
    with caplog.at_level("WARNING"):
        emit_user_warning(["summary.huge", "output"])
    msg = caplog.records[-1].getMessage()
    assert "2 field(s)" in msg
    assert "summary.huge" in msg
    assert "output" in msg
    assert "weave.publish" in msg


def test_walk_and_repackage_handles_all_shapes(client) -> None:
    """Covers under-threshold, oversize child, greedy bundle, oversize list/scalar, nested oversize."""
    obj = {"a": 1, "b": "small"}
    assert (
        _walk_and_repackage(obj, client=client, path=("summary",), repackaged=[])
        == obj
    )

    obj = {"small_a": 1, "small_b": "tiny", "huge": BIG_BLOB}
    paths: list[str] = []
    result = _walk_and_repackage(obj, client=client, path=("summary",), repackaged=paths)
    assert result["small_a"] == 1
    assert result["small_b"] == "tiny"
    assert result["huge"].startswith("weave:///")
    assert paths == ["summary.huge"]

    obj = {f"tiny_{i}": "z" for i in range(4)}
    for i in range(8):
        obj[f"med_{i}"] = "y" * 50_000
    result = _walk_and_repackage(obj, client=client, path=("summary",), repackaged=[])
    assert all(result[f"tiny_{i}"] == "z" for i in range(4))
    assert OVERFLOW_BUNDLE_KEY in result
    assert result[OVERFLOW_BUNDLE_KEY].startswith("weave:///")
    inline_meds = {k for k in result if k.startswith("med_")}
    assert inline_meds, "greedy batching should keep at least one medium inline"

    result = _walk_and_repackage(
        ["x" * 100_000] * 10, client=client, path=("output",), repackaged=[]
    )
    assert isinstance(result, str)
    assert result.startswith("weave:///")

    result = _walk_and_repackage(
        BIG_BLOB, client=client, path=("summary", "blob"), repackaged=[]
    )
    assert result.startswith("weave:///")

    obj = {"nested": {"deep": BIG_BLOB}, "smaller": "z" * 10_000}
    result = _walk_and_repackage(obj, client=client, path=("summary",), repackaged=[])
    assert result["nested"]["deep"].startswith("weave:///")
    assert result["smaller"] == "z" * 10_000
    assert OVERFLOW_BUNDLE_KEY not in result


def test_repackage_call_fields_passes_none_small_unchanged_and_hoists_oversize(
    client,
) -> None:
    new_fields, repackaged = repackage_call_fields(
        client, fields={"summary": None, "output": None}
    )
    assert new_fields == {"summary": None, "output": None}
    assert repackaged == []

    small = {"summary": {"weave": {"status": "ok"}}, "output": {"label": "ok"}}
    new_fields, repackaged = repackage_call_fields(client, fields=small)
    assert new_fields == small
    assert repackaged == []

    new_fields, repackaged = repackage_call_fields(
        client,
        fields={
            "inputs": {"prompt": "small", "context": BIG_BLOB},
            "output": {"label": "ok"},
            "summary": {"weave": {"usage": {"tokens": 5}}, "huge": BIG_BLOB},
        },
    )
    assert new_fields["inputs"]["prompt"] == "small"
    assert new_fields["inputs"]["context"].startswith("weave:///")
    assert new_fields["output"] == {"label": "ok"}
    assert new_fields["summary"]["weave"]["usage"]["tokens"] == 5
    assert new_fields["summary"]["huge"].startswith("weave:///")
    assert "inputs.context" in repackaged
    assert "summary.huge" in repackaged


def test_try_repackage_call_item_dispatches_all_three_item_shapes(
    client, monkeypatch
) -> None:
    """CompleteBatchItem, StartBatchItem, EndBatchItem + the two early-return paths."""
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: client)

    item = _complete_item(
        inputs={"prompt": "small"},
        output={"label": "ok", "blob": BIG_BLOB},
        summary={"weave": {"status": "ok"}},
    )
    new = _try_repackage_call_item(item)
    assert isinstance(new, CompleteBatchItem)
    assert new.req.output["blob"].startswith("weave:///")
    assert new.req.output["label"] == "ok"
    assert new.req.inputs == {"prompt": "small"}
    assert item.req.output["blob"] == BIG_BLOB  # source not mutated

    item = _start_item(inputs={"prompt": BIG_BLOB, "tag": "t"})
    new = _try_repackage_call_item(item)
    assert isinstance(new, StartBatchItem)
    assert new.req.start.inputs["prompt"].startswith("weave:///")
    assert new.req.start.inputs["tag"] == "t"

    item = _end_item(output={"blob": BIG_BLOB, "label": "ok"}, summary={"keep": "small"})
    new = _try_repackage_call_item(item)
    assert isinstance(new, EndBatchItem)
    assert new.req.end.output["blob"].startswith("weave:///")
    assert new.req.end.output["label"] == "ok"
    assert new.req.end.summary == {"keep": "small"}

    assert (
        _try_repackage_call_item(
            _end_item(output={"label": "ok"}, summary={"weave": {"status": "ok"}})
        )
        is None
    )

    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: None)
    assert _try_repackage_call_item(_end_item(output={"blob": BIG_BLOB})) is None


def test_try_repackage_call_end_req_hoists_oversize_and_skips_small(client) -> None:
    """Synchronous send_end_call path: oversize -> new req, small -> None."""
    big_req = _end_req_with_started_at(
        output={"blob": BIG_BLOB, "label": "ok"}, summary={"keep": "small"}
    )
    new_req = client._try_repackage_call_end_req(big_req)
    assert new_req is not None
    assert new_req.end.output["blob"].startswith("weave:///")
    assert new_req.end.output["label"] == "ok"
    assert new_req.end.summary == {"keep": "small"}

    small_req = _end_req_with_started_at(
        output={"label": "ok"}, summary={"weave": {"status": "ok"}}
    )
    assert client._try_repackage_call_end_req(small_req) is None


def test_flush_calls_eager_catches_413_repackages_and_retries(
    client, monkeypatch
) -> None:
    """v2 eager: 413 once, dispatcher repackages, resend succeeds."""
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: client)
    server = RemoteHTTPTraceServer.__new__(RemoteHTTPTraceServer)

    sent: list[tsi.EndedCallSchemaForInsertWithStartedAt] = []
    state = {"calls": 0}

    def fake_send_end(end):
        state["calls"] += 1
        if state["calls"] == 1:
            raise _make_http_error(413)
        sent.append(end)

    monkeypatch.setattr(server, "_send_call_end_v2", fake_send_end, raising=False)
    end_schema = tsi.EndedCallSchemaForInsertWithStartedAt(
        project_id="ent/proj",
        id="0199_end_id",
        started_at=datetime.datetime(2026, 5, 1),
        ended_at=datetime.datetime(2026, 5, 1, 0, 0, 1),
        output={"blob": BIG_BLOB, "label": "ok"},
        summary={"keep": "small"},
    )
    item = EndBatchItem(req=CallEndReq(end=end_schema))

    server._flush_calls_eager([item])

    assert state["calls"] == 2, "expected one 413 then one successful retry"
    assert len(sent) == 1
    resent = sent[0]
    assert resent.output["blob"].startswith("weave:///")
    assert resent.output["label"] == "ok"
    assert resent.summary == {"keep": "small"}


@pytest.mark.disable_logging_error_check
def test_flush_calls_eager_drops_when_non_413(client, monkeypatch) -> None:
    """Non-413 errors take the drop path; no retry, no repackage."""
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: client)
    server = RemoteHTTPTraceServer.__new__(RemoteHTTPTraceServer)

    state = {"calls": 0}

    def fake_send_end(end):
        state["calls"] += 1
        raise _make_http_error(500)

    monkeypatch.setattr(server, "_send_call_end_v2", fake_send_end, raising=False)
    item = _end_item(output={"blob": BIG_BLOB})

    server._flush_calls_eager([item])

    assert state["calls"] == 1, "non-413 must not trigger a retry"
