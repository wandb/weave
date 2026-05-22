"""Tests for the SDK-side oversize-payload repackage helper.

Covers the full surface used by all 4 production retry paths:
- 413 detection
- the greedy size-based walk (single oversize child, greedy batching of
  medium siblings, oversize lists/strings/nested-under-oversize-parent)
- `repackage_call_fields` field-level entry point (None / small / oversize)
- `_try_repackage_call_item` dispatcher across all 3 batch item shapes
- `_flush_calls_eager` end-to-end 413+retry through the v2 path
- user warning surface

The tests use the standard `client` fixture (real WeaveClient against the
test trace server) so that `_save_object` returns real refs and we never
need a fake client/ref stand-in.
"""

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
    repackage_oversize_payload,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallStartReq,
    CompletedCallSchemaForInsert,
    EndedCallSchemaForInsert,
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

# ---------------------------------------------------------------------------
# Helpers (top-level: no imports inside functions; reused across tests)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 413 detection + warning surface (small, no client needed)
# ---------------------------------------------------------------------------


def test_413_detection_only_matches_payload_too_large() -> None:
    assert is_payload_too_large_error(_make_http_error(413)) is True
    # Anything else, including adjacent 4xx/5xx, must not match.
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
    assert "weave.publish" in msg  # guidance line


# ---------------------------------------------------------------------------
# Walk shapes — all the algorithmic cases in one assertion-rich test
# ---------------------------------------------------------------------------


def test_walk_and_repackage_handles_all_shapes(client) -> None:
    """One pass covering every branch the walk needs to take:
    - under-threshold dict stays intact
    - oversize child gets hoisted; small siblings stay inline
    - many medium siblings get bundled via greedy batching
    - oversize list is published whole
    - oversize scalar string gets published
    - nested oversize-under-oversize-parent hoists only the inner child
    """
    # Under threshold: returns input unchanged, no publish
    obj = {"a": 1, "b": "small"}
    assert (
        _walk_and_repackage(obj, client=client, path=("summary",), repackaged=[])
        == obj
    )

    # Oversize child + small siblings
    obj = {"small_a": 1, "small_b": "tiny", "huge": BIG_BLOB}
    paths: list[str] = []
    result = _walk_and_repackage(obj, client=client, path=("summary",), repackaged=paths)
    assert result["small_a"] == 1
    assert result["small_b"] == "tiny"
    assert result["huge"].startswith("weave:///")
    assert paths == ["summary.huge"]

    # Greedy batching: 4 tiny + 8 medium (~50KiB) siblings, threshold ~256KiB
    obj = {f"tiny_{i}": "z" for i in range(4)}
    for i in range(8):
        obj[f"med_{i}"] = "y" * 50_000
    result = _walk_and_repackage(obj, client=client, path=("summary",), repackaged=[])
    assert all(result[f"tiny_{i}"] == "z" for i in range(4))
    assert OVERFLOW_BUNDLE_KEY in result
    assert result[OVERFLOW_BUNDLE_KEY].startswith("weave:///")
    # Every medium sibling shows up either inline or inside the bundle ref
    # (we don't dereference the ref here — coverage of bundle contents lives
    # in the unit test for `_greedy_batch`).
    inline_meds = {k for k in result if k.startswith("med_")}
    assert inline_meds, "greedy batching should keep at least one medium inline"

    # Oversize list -> published whole
    result = _walk_and_repackage(
        ["x" * 100_000] * 10, client=client, path=("output",), repackaged=[]
    )
    assert isinstance(result, str)
    assert result.startswith("weave:///")

    # Oversize scalar string -> published
    result = _walk_and_repackage(
        BIG_BLOB, client=client, path=("summary", "blob"), repackaged=[]
    )
    assert result.startswith("weave:///")

    # Nested oversize-under-oversize parent: only inner child hoists
    obj = {"nested": {"deep": BIG_BLOB}, "smaller": "z" * 10_000}
    result = _walk_and_repackage(obj, client=client, path=("summary",), repackaged=[])
    assert result["nested"]["deep"].startswith("weave:///")
    assert result["smaller"] == "z" * 10_000
    assert OVERFLOW_BUNDLE_KEY not in result


# ---------------------------------------------------------------------------
# Field-level entry point
# ---------------------------------------------------------------------------


def test_repackage_call_fields_passes_none_small_unchanged_and_hoists_oversize(
    client,
) -> None:
    # Nones round-trip as None (not "{}").
    new_fields, repackaged = repackage_call_fields(
        client, fields={"summary": None, "output": None}
    )
    assert new_fields == {"summary": None, "output": None}
    assert repackaged == []

    # Small values pass through identically.
    small = {"summary": {"weave": {"status": "ok"}}, "output": {"label": "ok"}}
    new_fields, repackaged = repackage_call_fields(client, fields=small)
    assert new_fields == small
    assert repackaged == []

    # Oversize subtrees get hoisted; small siblings remain.
    new_fields, repackaged = repackage_call_fields(
        client,
        fields={
            "inputs": {"prompt": "small", "context": BIG_BLOB},
            "output": {"label": "ok"},
        },
    )
    assert new_fields["inputs"]["prompt"] == "small"
    assert new_fields["inputs"]["context"].startswith("weave:///")
    assert new_fields["output"] == {"label": "ok"}
    assert "inputs.context" in repackaged

    # `repackage_oversize_payload` is just sugar over the above; verify
    # summary + output are walked independently and both pick up refs.
    new_summary, new_output, repackaged = repackage_oversize_payload(
        client,
        summary={"weave": {"usage": {"tokens": 5}}, "huge": BIG_BLOB},
        output=BIG_BLOB,
    )
    assert new_summary["weave"]["usage"]["tokens"] == 5
    assert new_summary["huge"].startswith("weave:///")
    assert isinstance(new_output, str)
    assert new_output.startswith("weave:///")
    assert "summary.huge" in repackaged
    assert "output" in repackaged


# ---------------------------------------------------------------------------
# _try_repackage_call_item — the one dispatcher used by all 3 batched paths
# ---------------------------------------------------------------------------


def test_try_repackage_call_item_dispatches_all_three_item_shapes(
    client, monkeypatch
) -> None:
    """One test verifies the dispatcher works for CompleteBatchItem,
    StartBatchItem, and EndBatchItem, plus the two early-return paths
    (no client, nothing to shrink). All 3 batched flush paths route through
    this single function; covering it here is the full DRY contract.
    """
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: client)

    # CompleteBatchItem: output gets hoisted; inputs unchanged.
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
    # Source item unmodified
    assert item.req.output["blob"] == BIG_BLOB

    # StartBatchItem: inputs get hoisted.
    item = _start_item(inputs={"prompt": BIG_BLOB, "tag": "t"})
    new = _try_repackage_call_item(item)
    assert isinstance(new, StartBatchItem)
    assert new.req.start.inputs["prompt"].startswith("weave:///")
    assert new.req.start.inputs["tag"] == "t"

    # EndBatchItem: output gets hoisted, summary preserved.
    item = _end_item(output={"blob": BIG_BLOB, "label": "ok"}, summary={"keep": "small"})
    new = _try_repackage_call_item(item)
    assert isinstance(new, EndBatchItem)
    assert new.req.end.output["blob"].startswith("weave:///")
    assert new.req.end.output["label"] == "ok"
    assert new.req.end.summary == {"keep": "small"}

    # Nothing oversize -> None (skip the retry, drop falls through).
    assert (
        _try_repackage_call_item(
            _end_item(output={"label": "ok"}, summary={"weave": {"status": "ok"}})
        )
        is None
    )

    # No active client -> None.
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: None)
    assert (
        _try_repackage_call_item(_end_item(output={"blob": BIG_BLOB})) is None
    )


# ---------------------------------------------------------------------------
# Eager flush (v2 single endpoints) — end-to-end 413 + retry
# ---------------------------------------------------------------------------


def test_flush_calls_eager_catches_413_repackages_and_retries(
    client, monkeypatch
) -> None:
    """The v2 eager path: `_send_call_end_v2` returns 413 once, the eager
    flush invokes `_try_repackage_call_item`, then resends and succeeds.
    """
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
    # Eager processor only inspects EndBatchItem.req.end / StartBatchItem.req.start
    # and dispatches to _send_call_*_v2. Build an EndBatchItem whose req.end
    # carries the started_at expected by the v2 endpoint contract.
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
    """Non-413 errors take the original drop path; no retry, no repackage."""
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: client)
    server = RemoteHTTPTraceServer.__new__(RemoteHTTPTraceServer)

    state = {"calls": 0}

    def fake_send_end(end):
        state["calls"] += 1
        raise _make_http_error(500)

    monkeypatch.setattr(server, "_send_call_end_v2", fake_send_end, raising=False)
    item = _end_item(output={"blob": BIG_BLOB})

    # Should not raise; drop logging happens internally.
    server._flush_calls_eager([item])

    assert state["calls"] == 1, "non-413 must not trigger a retry"
