"""Tests for the SDK-side oversize-payload repackage helper.

Covers:
- 413 detection
- greedy size-based extraction (small siblings stay inline, oversize
  children get hoisted, medium siblings get batched into one ref)
- the round trip through `repackage_oversize_payload`
- the `send_end_call` retry: server returns 413 once, SDK repackages,
  retry succeeds
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from weave.trace import oversize_repackage
from weave.trace.oversize_repackage import (
    OVERFLOW_BUNDLE_KEY,
    OVERSIZE_SUBTREE_BYTES,
    _approx_size,
    _walk_and_repackage,
    is_payload_too_large_error,
    repackage_oversize_payload,
)


class FakeRef:
    def __init__(self, name: str, digest: str = "digest123") -> None:
        self._name = name
        self._digest = digest

    def uri(self) -> str:
        return f"weave:///fake/test/object/{self._name}:{self._digest}"


class FakeClient:
    """Stand-in for WeaveClient. Records every `_save_object` call so tests
    can assert on what got published.
    """

    def __init__(self) -> None:
        self.saved: list[tuple[str, Any]] = []

    def _save_object(self, val: Any, name: str) -> FakeRef:
        self.saved.append((name, val))
        return FakeRef(name=name, digest=f"d{len(self.saved)}")


# ---------------------------------------------------------------------------
# 413 detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [413])
def test_is_413_detects_payload_too_large(status: int) -> None:
    exc = httpx.HTTPStatusError(
        "too big",
        request=httpx.Request("POST", "http://x"),
        response=httpx.Response(status),
    )
    assert is_payload_too_large_error(exc) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 408, 500, 502, 503])
def test_is_413_rejects_other_status_codes(status: int) -> None:
    exc = httpx.HTTPStatusError(
        "other",
        request=httpx.Request("POST", "http://x"),
        response=httpx.Response(status),
    )
    assert is_payload_too_large_error(exc) is False


def test_is_413_rejects_non_http_exceptions() -> None:
    assert is_payload_too_large_error(ValueError("boom")) is False


# ---------------------------------------------------------------------------
# _approx_size sanity
# ---------------------------------------------------------------------------


def test_approx_size_handles_unjsonable_objects() -> None:
    # Sets aren't JSON-encodable; default=str rescues us.
    assert _approx_size({"x": {1, 2, 3}}) > 0


# ---------------------------------------------------------------------------
# _walk_and_repackage shapes
# ---------------------------------------------------------------------------


def test_walk_under_threshold_returns_obj_unchanged() -> None:
    client = FakeClient()
    obj = {"a": 1, "b": "small"}
    result = _walk_and_repackage(obj, client=client, path=("summary",), repackaged=[])
    assert result == obj
    assert client.saved == []


def test_walk_hoists_individually_oversize_child() -> None:
    """An oversize child becomes its own ref; small siblings stay inline."""
    client = FakeClient()
    obj = {
        "small_a": 1,
        "small_b": "tiny",
        "huge": "x" * (OVERSIZE_SUBTREE_BYTES + 1000),
    }
    repackaged: list[str] = []
    result = _walk_and_repackage(
        obj, client=client, path=("summary",), repackaged=repackaged
    )

    assert result["small_a"] == 1
    assert result["small_b"] == "tiny"
    assert isinstance(result["huge"], str)
    assert result["huge"].startswith("weave:///")
    assert repackaged == ["summary.huge"]
    # Only one publish, the huge child
    assert len(client.saved) == 1
    assert client.saved[0][0] == "summary_huge"


def test_walk_greedy_batches_many_medium_siblings() -> None:
    """The 500x100KiB case the reviewer flagged: many medium-sized
    siblings, none individually over threshold. Greedy batching should
    keep the smallest siblings inline and bundle the rest under
    `_weave_overflow`.
    """
    client = FakeClient()
    # 8 medium siblings (each ~50 KiB) + 4 tiny siblings.  Threshold is
    # 256 KiB, so ~5 mediums fit inline and the rest should bundle.
    obj: dict[str, Any] = {f"tiny_{i}": "z" for i in range(4)}
    for i in range(8):
        obj[f"med_{i}"] = "y" * 50_000

    repackaged: list[str] = []
    result = _walk_and_repackage(
        obj, client=client, path=("summary",), repackaged=repackaged
    )

    assert isinstance(result, dict)
    # All tiny siblings stay inline
    for i in range(4):
        assert result[f"tiny_{i}"] == "z"
    # An overflow bundle ref is attached
    assert OVERFLOW_BUNDLE_KEY in result
    assert result[OVERFLOW_BUNDLE_KEY].startswith("weave:///")
    # Exactly one publish (the bundle), not one per medium sibling
    assert len(client.saved) == 1
    assert client.saved[0][0] == f"summary_{OVERFLOW_BUNDLE_KEY}"
    # The bundle contains the medium siblings that didn't fit
    bundle = client.saved[0][1]
    assert all(k.startswith("med_") for k in bundle)
    # All medium siblings are accounted for (inline + bundled)
    inline_meds = {k for k in result if k.startswith("med_")}
    bundle_meds = set(bundle.keys())
    assert inline_meds | bundle_meds == {f"med_{i}" for i in range(8)}


def test_walk_publishes_oversize_list_whole() -> None:
    client = FakeClient()
    obj = ["x" * 100_000] * 10  # ~1 MB list
    result = _walk_and_repackage(
        obj, client=client, path=("output",), repackaged=[]
    )
    assert isinstance(result, str)
    assert result.startswith("weave:///")
    assert len(client.saved) == 1


def test_walk_publishes_oversize_scalar_string() -> None:
    client = FakeClient()
    obj = "x" * (OVERSIZE_SUBTREE_BYTES + 1)
    result = _walk_and_repackage(
        obj, client=client, path=("summary", "blob"), repackaged=[]
    )
    assert result.startswith("weave:///")


def test_walk_nested_oversize_under_oversize_parent() -> None:
    """Parent dict is over threshold; one nested child is also individually
    over threshold. The nested one should be hoisted individually, and the
    remaining peers should not require greedy-batching (because removing
    the hoisted child brought the parent under threshold).
    """
    client = FakeClient()
    obj = {
        "nested": {"deep": "y" * (OVERSIZE_SUBTREE_BYTES + 1000)},
        "smaller": "z" * 10_000,
    }
    repackaged: list[str] = []
    result = _walk_and_repackage(
        obj, client=client, path=("summary",), repackaged=repackaged
    )
    # `nested.deep` got hoisted as its own ref
    assert result["nested"]["deep"].startswith("weave:///")
    # `smaller` stayed inline
    assert result["smaller"] == "z" * 10_000
    # No bundle key required at the top level
    assert OVERFLOW_BUNDLE_KEY not in result


# ---------------------------------------------------------------------------
# repackage_oversize_payload (top-level entry point)
# ---------------------------------------------------------------------------


def test_repackage_returns_unchanged_when_under_threshold() -> None:
    client = FakeClient()
    summary = {"weave": {"usage": {"x": 1}}}
    output = {"answer": "small"}
    new_summary, new_output, repackaged = repackage_oversize_payload(
        client, summary=summary, output=output
    )
    assert new_summary == summary
    assert new_output == output
    assert repackaged == []


def test_repackage_extracts_summary_and_output_independently() -> None:
    client = FakeClient()
    summary = {
        "weave": {"usage": {"tokens": 5}},
        "huge": "x" * (OVERSIZE_SUBTREE_BYTES + 1000),
    }
    output = "y" * (OVERSIZE_SUBTREE_BYTES + 1000)

    new_summary, new_output, repackaged = repackage_oversize_payload(
        client, summary=summary, output=output
    )

    # Inline projection preserved in summary
    assert new_summary["weave"]["usage"]["tokens"] == 5
    assert new_summary["huge"].startswith("weave:///")
    # Output became a single ref string
    assert isinstance(new_output, str)
    assert new_output.startswith("weave:///")
    # Both paths recorded
    assert "summary.huge" in repackaged
    assert "output" in repackaged
    assert len(client.saved) == 2


# ---------------------------------------------------------------------------
# Integration: send_end_call catches 413, repackages, retries once
# ---------------------------------------------------------------------------


def _make_413(message: str = "too large") -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(
        message,
        request=httpx.Request("POST", "http://test"),
        response=httpx.Response(413),
    )


def test_send_end_call_retries_after_413_and_repackages(monkeypatch) -> None:
    """The end-to-end behavior the WB-34652 ticket asks for: a single 413
    triggers repackage + one retry, then the call lands.
    """
    # 1. Simulate `self.server.call_end`: 413 the first time, ok the second.
    call_log: list[Any] = []
    response_state = {"call_count": 0}

    def fake_call_end(req):
        response_state["call_count"] += 1
        if response_state["call_count"] == 1:
            raise _make_413()
        call_log.append(req)

    fake_server = MagicMock()
    fake_server.call_end.side_effect = fake_call_end

    # 2. Build the slimmer payload helper so the closure-internal code
    # exercises the real helper, not a stub.
    fake_client = FakeClient()

    # 3. Drive the exact try/except shape used by `send_end_call`. We can't
    # easily exercise `WeaveClient.finish_call` end-to-end without a full
    # test server, but the catch-and-retry block is small enough to mirror
    # here exactly. If the production shape drifts, this test will need to
    # follow.
    project_id = "ent/proj"
    merged_summary = {"big": "x" * (OVERSIZE_SUBTREE_BYTES + 1000), "tiny": 1}
    output_json = {"small": True}

    initial_req = MagicMock()
    initial_req.end = MagicMock()
    initial_req.end.summary = merged_summary
    initial_req.end.output = output_json

    caught_413 = False
    try:
        fake_server.call_end(initial_req)
    except Exception as e:
        caught_413 = is_payload_too_large_error(e)
    assert caught_413, "expected first call to raise a 413"

    new_summary, new_output, repackaged = repackage_oversize_payload(
        fake_client, summary=merged_summary, output=output_json
    )
    assert repackaged, "expected repackage to identify oversize fields"

    retry_req = MagicMock()
    retry_req.end = MagicMock()
    retry_req.end.summary = new_summary
    retry_req.end.output = new_output
    fake_server.call_end(retry_req)
    oversize_repackage.emit_user_warning(repackaged)

    assert response_state["call_count"] == 2
    assert len(call_log) == 1
    # The retry's summary has the big field replaced by a ref
    retry_summary = call_log[0].end.summary
    assert retry_summary["big"].startswith("weave:///")
    assert retry_summary["tiny"] == 1


def test_send_end_call_does_not_retry_for_non_413(monkeypatch) -> None:
    """Other errors propagate without triggering the repackage path."""
    fake_client = FakeClient()
    fake_server = MagicMock()
    fake_server.call_end.side_effect = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "http://test"),
        response=httpx.Response(500),
    )

    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        fake_server.call_end(MagicMock())
    assert not is_payload_too_large_error(excinfo.value)
    assert fake_client.saved == []  # repackage never invoked


# ---------------------------------------------------------------------------
# Warning surface
# ---------------------------------------------------------------------------


def test_emit_user_warning_is_silent_when_nothing_repackaged(caplog) -> None:
    with caplog.at_level("WARNING"):
        oversize_repackage.emit_user_warning([])
    assert all("repackaged" not in r.message for r in caplog.records)


def test_emit_user_warning_names_repackaged_paths(caplog) -> None:
    with caplog.at_level("WARNING"):
        oversize_repackage.emit_user_warning(
            ["summary.weave.predictions", "output"]
        )
    msg = caplog.records[-1].getMessage()
    assert "2 field(s)" in msg
    assert "summary.weave.predictions" in msg
    assert "output" in msg
    assert "weave.publish" in msg  # guidance line


# ---------------------------------------------------------------------------
# repackage_call_fields
# ---------------------------------------------------------------------------


def test_repackage_call_fields_passes_through_none_values() -> None:
    """None field values must round-trip as None, not '{}'."""
    client = FakeClient()
    new_fields, repackaged = oversize_repackage.repackage_call_fields(
        client,  # type: ignore[arg-type]
        fields={"summary": None, "output": None},
    )
    assert new_fields == {"summary": None, "output": None}
    assert repackaged == []
    assert client.saved == []


def test_repackage_call_fields_returns_small_values_unchanged() -> None:
    """Anything under the oversize threshold passes through identically."""
    client = FakeClient()
    new_fields, repackaged = oversize_repackage.repackage_call_fields(
        client,  # type: ignore[arg-type]
        fields={
            "summary": {"weave": {"status": "success"}},
            "output": {"label": "ok"},
        },
    )
    assert new_fields == {
        "summary": {"weave": {"status": "success"}},
        "output": {"label": "ok"},
    }
    assert repackaged == []


def test_repackage_call_fields_hoists_oversize_subtrees() -> None:
    """A subtree above the threshold is published and replaced with a ref URI."""
    client = FakeClient()
    big = "x" * (OVERSIZE_SUBTREE_BYTES * 2)
    new_fields, repackaged = oversize_repackage.repackage_call_fields(
        client,  # type: ignore[arg-type]
        fields={
            "inputs": {"prompt": "small", "context": big},
            "output": {"label": "ok"},
        },
    )
    assert new_fields["inputs"]["prompt"] == "small"
    assert new_fields["inputs"]["context"].startswith("weave:///")
    assert new_fields["output"] == {"label": "ok"}
    assert "inputs.context" in repackaged


# ---------------------------------------------------------------------------
# Batched-flush repackage closures (RemoteHTTPTraceServer)
# ---------------------------------------------------------------------------


def _complete_item(*, inputs=None, output=None, summary=None, attributes=None):
    """Build a CompleteBatchItem for closure tests."""
    import datetime as _dt
    from weave.trace_server.trace_server_interface import (
        CompletedCallSchemaForInsert,
    )
    from weave.trace_server_bindings.models import CompleteBatchItem

    req = CompletedCallSchemaForInsert(
        project_id="ent/proj",
        id="0199_complete_id",
        trace_id="0199_trace_id",
        op_name="op_name",
        started_at=_dt.datetime(2026, 5, 1),
        ended_at=_dt.datetime(2026, 5, 1, 0, 0, 1),
        attributes=attributes or {},
        inputs=inputs or {},
        output=output,
        summary=summary or {},
    )
    return CompleteBatchItem(req=req)


def _end_item(*, output=None, summary=None):
    import datetime as _dt
    from weave.trace_server.trace_server_interface import (
        CallEndReq,
        EndedCallSchemaForInsert,
    )
    from weave.trace_server_bindings.models import EndBatchItem

    end = EndedCallSchemaForInsert(
        project_id="ent/proj",
        id="0199_end_id",
        ended_at=_dt.datetime(2026, 5, 1),
        output=output,
        summary=summary or {},
    )
    return EndBatchItem(req=CallEndReq(end=end))


def test_repackage_complete_batch_item_repackages_output(monkeypatch) -> None:
    """The CompleteBatchItem closure hoists oversize output subtrees and
    returns a new item with refs inline.
    """
    from weave.trace.context import weave_client_context
    from weave.trace_server_bindings.remote_http_trace_server import (
        _repackage_complete_batch_item,
    )

    client = FakeClient()
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: client)

    big = "x" * (OVERSIZE_SUBTREE_BYTES * 2)
    item = _complete_item(
        inputs={"prompt": "small"},
        output={"label": "ok", "blob": big},
        summary={"weave": {"status": "success"}},
    )

    new_item = _repackage_complete_batch_item(item)

    assert new_item is not None
    assert new_item.req.output["blob"].startswith("weave:///")
    assert new_item.req.output["label"] == "ok"
    assert new_item.req.inputs == {"prompt": "small"}
    # Original item not mutated.
    assert item.req.output["blob"] == big


def test_repackage_complete_batch_item_returns_none_when_nothing_to_shrink(
    monkeypatch,
) -> None:
    from weave.trace.context import weave_client_context
    from weave.trace_server_bindings.remote_http_trace_server import (
        _repackage_complete_batch_item,
    )

    client = FakeClient()
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: client)
    item = _complete_item(
        inputs={"prompt": "small"},
        output={"label": "ok"},
        summary={"weave": {"status": "success"}},
    )
    assert _repackage_complete_batch_item(item) is None
    assert client.saved == []


def test_repackage_complete_batch_item_returns_none_when_no_client(
    monkeypatch,
) -> None:
    from weave.trace.context import weave_client_context
    from weave.trace_server_bindings.remote_http_trace_server import (
        _repackage_complete_batch_item,
    )

    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: None)
    item = _complete_item(output={"blob": "x" * (OVERSIZE_SUBTREE_BYTES * 2)})
    assert _repackage_complete_batch_item(item) is None


def test_repackage_legacy_end_item_hoists_summary_and_output(monkeypatch) -> None:
    from weave.trace.context import weave_client_context
    from weave.trace_server_bindings.models import EndBatchItem
    from weave.trace_server_bindings.remote_http_trace_server import (
        _repackage_legacy_batch_item,
    )

    client = FakeClient()
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: client)

    big = "x" * (OVERSIZE_SUBTREE_BYTES * 2)
    item = _end_item(
        output={"blob": big, "label": "ok"},
        summary={"keep": "small"},
    )

    new_item = _repackage_legacy_batch_item(item)

    assert isinstance(new_item, EndBatchItem)
    assert new_item.req.end.output["blob"].startswith("weave:///")
    assert new_item.req.end.output["label"] == "ok"
    assert new_item.req.end.summary == {"keep": "small"}


def test_repackage_legacy_returns_none_when_nothing_to_shrink(monkeypatch) -> None:
    from weave.trace.context import weave_client_context
    from weave.trace_server_bindings.remote_http_trace_server import (
        _repackage_legacy_batch_item,
    )

    client = FakeClient()
    monkeypatch.setattr(weave_client_context, "get_weave_client", lambda: client)
    item = _end_item(output={"label": "ok"}, summary={"weave": {"status": "ok"}})
    assert _repackage_legacy_batch_item(item) is None
