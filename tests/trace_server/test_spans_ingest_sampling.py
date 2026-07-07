"""Tests for the spans-model ingest sampler (agents/ingest_sampling.py).

The pure decision/hash tests need no backend. The end-to-end ingest tests run
the real OTel export path against ClickHouse via the ``ch_server`` fixture.
See WB-36877.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
from unittest.mock import MagicMock

import pytest
from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource as PbResource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan

from tests.trace_server.helpers import make_project_id
from weave.trace_server import environment
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents import ingest_sampling, ingest_sampling_metrics
from weave.trace_server.agents.types import (
    AgentSpansQueryReq,
    AgentSpanValueRef,
    GenAIOTelExportReq,
)
from weave.trace_server.base64_content_conversion import AUTO_CONVERSION_MIN_SIZE
from weave.trace_server.opentelemetry.helpers import (
    AttributePathConflictError,
    unflatten_key_values,
)
from weave.trace_server.opentelemetry.python_spans import Resource as PyResource
from weave.trace_server.opentelemetry.python_spans import Span as PySpan
from weave.trace_server.opentelemetry.python_spans import StatusCode

EVAL_MARKER_ATTR = "weave.eval.predict_and_score_call_id"
STAMP_ATTR = "weave.ingest_sample_rate"

_NOW_NS = int(datetime.datetime(2026, 1, 1).timestamp() * 1_000_000_000)


def _proto_span(
    trace_id: bytes,
    span_id: bytes,
    *,
    parent_span_id: bytes | None = None,
    attrs: dict[str, str | float] | None = None,
    name: str = "chat test-model",
) -> PbSpan:
    """Build a minimal ended OTel proto span (no parent -> a turn root)."""
    span = PbSpan()
    span.name = name
    span.trace_id = trace_id
    span.span_id = span_id
    if parent_span_id is not None:
        span.parent_span_id = parent_span_id
    span.start_time_unix_nano = _NOW_NS
    span.end_time_unix_nano = _NOW_NS + 1_000_000_000
    span.kind = 1  # CLIENT
    for key, value in (attrs or {}).items():
        kv = KeyValue()
        kv.key = key
        if isinstance(value, float):
            kv.value.double_value = value
        else:
            kv.value.string_value = value
        span.attributes.append(kv)
    span.status.code = StatusCode.OK.value  # type: ignore[assignment]
    return span


def _processed(*spans: PbSpan, run_id: str | None = None) -> tsi.ProcessedResourceSpans:
    scope = InstrumentationScope()
    scope.name = "test_instrumentation"
    scope.version = "1.0.0"
    scope_spans = ScopeSpans()
    scope_spans.scope.CopyFrom(scope)
    scope_spans.spans.extend(spans)
    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(PbResource())
    resource_spans.scope_spans.append(scope_spans)
    return tsi.ProcessedResourceSpans(
        entity="test-entity",
        project="test-project",
        run_id=run_id,
        resource_spans=resource_spans,
    )


def _export(ch_server, project_id: str, *spans: PbSpan):
    return ch_server.genai_otel_export(
        GenAIOTelExportReq(
            processed_spans=[_processed(*spans)],
            project_id=project_id,
            wb_user_id="test-user",
        )
    )


def _stored_spans(ch_server, project_id: str):
    # Custom-attr Maps are returned only for explicitly selected keys, so ask
    # for the stamp key in both typed maps it could land in.
    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            custom_attr_columns=[
                AgentSpanValueRef(source="custom_attrs_float", key=STAMP_ATTR),
                AgentSpanValueRef(source="custom_attrs_string", key=STAMP_ATTR),
            ],
        )
    )
    return res.spans


def _parse(span: PbSpan) -> PySpan:
    return PySpan.from_proto(span, PyResource.from_proto(PbResource()))


def _conflict_error(span: PbSpan) -> str:
    """The exact parse-failure message the server records for this span."""
    with pytest.raises(AttributePathConflictError) as excinfo:
        unflatten_key_values(span.attributes)
    return str(excinfo.value)


def _tid_with_verdict(rate: float, *, kept: bool, start: int = 1) -> bytes:
    """First 16-byte trace id (from ``start`` upward) whose verdict matches."""
    for i in range(start, start + 10_000):
        tid = i.to_bytes(16, "big")
        if ingest_sampling.keep_by_hash(tid.hex(), rate) == kept:
            return tid
    raise AssertionError(f"no trace id with kept={kept} at rate={rate} in range")


@pytest.fixture
def sampler_metrics(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """Record sampler metric emissions instead of sending UDP packets."""
    calls: dict[str, list] = {
        "seen": [],
        "parse_failures": [],
        "evals_kept": [],
        "dropped": [],
    }
    monkeypatch.setattr(ingest_sampling_metrics, "seen", calls["seen"].append)
    monkeypatch.setattr(
        ingest_sampling_metrics, "parse_failures", calls["parse_failures"].append
    )
    monkeypatch.setattr(
        ingest_sampling_metrics, "evals_kept", calls["evals_kept"].append
    )
    monkeypatch.setattr(
        ingest_sampling_metrics,
        "dropped",
        lambda c, b, d: calls["dropped"].append((c, b, d)),
    )
    return calls


# --- pure functions ---------------------------------------------------------


def test_keep_by_hash_matches_inline_sha256() -> None:
    # Pin the exact formula: the calls-model sampler uses the same one, and a
    # trace living in both data models must get one verdict. Purity also gives
    # cross-request determinism: the verdict depends on nothing but the string.
    for i in range(1, 50):
        tid = i.to_bytes(16, "big").hex()
        for rate in (0.0, 0.1, 0.5, 0.9, 1.0):
            expected = (
                int(hashlib.sha256(tid.encode("utf-8")).hexdigest(), 16) % 1_000_000
            ) < rate * 1_000_000
            assert ingest_sampling.keep_by_hash(tid, rate) is expected


def test_keep_by_hash_rate_extremes() -> None:
    ids = [i.to_bytes(16, "big").hex() for i in range(1, 201)]
    assert all(ingest_sampling.keep_by_hash(tid, 1.0) for tid in ids)
    assert not any(ingest_sampling.keep_by_hash(tid, 0.0) for tid in ids)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.1", 0.1),  # valid
        ("0.0", 0.0),  # valid edge (drop all non-eval)
        ("1.0", 1.0),  # valid edge (off)
        ("-1", 1.0),  # negative would drop everything -> fall back to off
        ("2.0", 1.0),  # above range -> off
        ("nan", 1.0),  # NaN fails the range check -> off
        ("inf", 1.0),  # inf fails the range check -> off
        ("abc", 1.0),  # unparseable -> off
    ],
)
def test_sample_rate_env_falls_back_to_off_when_invalid(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: float
) -> None:
    # Validation parity with the calls-model sampler: both read this variable,
    # so a drift here would give the two models different effective rates.
    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", value)
    assert environment.wf_ingest_sample_rate() == expected


@pytest.mark.parametrize(
    ("trace_id_bytes", "usable"),
    [
        (b"\xaa" * 16, True),
        (b"", False),  # empty proto bytes
        (b"\xab" * 15, False),  # 15-byte id
        (b"\xab" * 17, False),  # 17-byte id
        (b"\x00" * 16, False),  # OTel-invalid zero id
    ],
)
def test_unusable_trace_ids_fail_open_in_decisions(
    sampler_metrics: dict[str, list], trace_id_bytes: bytes, usable: bool
) -> None:
    # At rate 0.0 a usable id is hash-dropped; an unusable one is kept
    # fail-open and counted as a parse failure.
    config = ingest_sampling.SamplingConfig(rate=0.0, dry_run=False)
    span = _parse(_proto_span(trace_id_bytes, b"\x0a" * 8))
    decisions = ingest_sampling.decide_spans(config, [span], [5])
    if usable:
        assert decisions == [ingest_sampling.SpanDecision(drop=True)]
        assert sampler_metrics["parse_failures"] == []
    else:
        assert decisions == [ingest_sampling.SpanDecision(drop=False)]
        assert sampler_metrics["parse_failures"] == [1]


# --- decision ladder (parsed spans, no backend) -----------------------------


def test_decide_spans_ladder_at_rate_zero(sampler_metrics: dict[str, list]) -> None:
    config = ingest_sampling.SamplingConfig(rate=0.0, dry_run=False)
    eval_tid = (1).to_bytes(16, "big")
    plain_tid = (2).to_bytes(16, "big")
    spans = [
        _parse(_proto_span(b"", b"\x01" * 8)),  # unusable id -> fail open
        _parse(_proto_span(eval_tid, b"\x02" * 8, attrs={EVAL_MARKER_ATTR: "pas-1"})),
        # Unmarked child of the eval trace: protected by its marked sibling.
        _parse(_proto_span(eval_tid, b"\x03" * 8)),
        _parse(_proto_span(plain_tid, b"\x04" * 8)),
    ]
    decisions = ingest_sampling.decide_spans(config, spans, [10, 20, 30, 40])
    assert decisions == [
        ingest_sampling.SpanDecision(drop=False),
        ingest_sampling.SpanDecision(drop=False),
        ingest_sampling.SpanDecision(drop=False),
        ingest_sampling.SpanDecision(drop=True),
    ]
    # Counters are per span but emitted once per request (aggregated).
    assert sampler_metrics["seen"] == [4]
    assert sampler_metrics["parse_failures"] == [1]
    assert sampler_metrics["evals_kept"] == [2]
    assert sampler_metrics["dropped"] == [(1, 40, False)]


def test_decide_spans_dry_run_keeps_but_counts(
    sampler_metrics: dict[str, list],
) -> None:
    config = ingest_sampling.SamplingConfig(rate=0.0, dry_run=True)
    span = _parse(_proto_span((3).to_bytes(16, "big"), b"\x05" * 8))
    decisions = ingest_sampling.decide_spans(config, [span], [17])
    # Dry-run never drops, and a dry-run hash winner gets no rate either.
    assert decisions == [ingest_sampling.SpanDecision(drop=False, sampled_rate=None)]
    assert sampler_metrics["dropped"] == [(1, 17, True)]


def test_decide_spans_rate_stamp_only_on_genuine_hash_keep(
    sampler_metrics: dict[str, list],
) -> None:
    rate = 0.5
    kept_tid = _tid_with_verdict(rate, kept=True)
    # A different hash-winning trace id, so the eval trace stays separate.
    eval_tid = _tid_with_verdict(
        rate, kept=True, start=int.from_bytes(kept_tid, "big") + 1
    )
    assert eval_tid != kept_tid
    config = ingest_sampling.SamplingConfig(rate=rate, dry_run=False)
    spans = [
        _parse(_proto_span(kept_tid, b"\x06" * 8)),
        # Eval trace with a hash-winning id: kept whole, so no stamp.
        _parse(_proto_span(eval_tid, b"\x07" * 8, attrs={EVAL_MARKER_ATTR: "pas-2"})),
    ]
    decisions = ingest_sampling.decide_spans(config, spans, [1, 1])
    assert decisions == [
        ingest_sampling.SpanDecision(drop=False, sampled_rate=0.5),
        ingest_sampling.SpanDecision(drop=False, sampled_rate=None),
    ]


# --- end-to-end ingest (ClickHouse) -----------------------------------------

# CI ClickHouse occasionally doesn't surface a just-inserted span to the
# immediate read (same reruns guard as the other genai ingest tests).


@pytest.mark.flaky(reruns=3)
@pytest.mark.parametrize("rate_env", [None, "1.0"], ids=["unset", "explicit-1.0"])
def test_sampler_off_is_inert(
    ch_server,
    sampler_metrics: dict[str, list],
    monkeypatch: pytest.MonkeyPatch,
    rate_env: str | None,
) -> None:
    """The default config must not change ingest behavior at all.

    Pins the exact error_message (content and per-span order) on a request
    mixing good spans with two distinct parse failures. Extraction failures
    share the same extract_row helper in both branches, but no real OTel
    payload can make the defensively-guarded extractor raise, so that branch
    is covered by construction rather than by a fixture.
    """
    if rate_env is None:
        monkeypatch.delenv("WEAVE_INGEST_SAMPLE_RATE", raising=False)
    else:
        monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", rate_env)
    project_id = make_project_id("spans_sampling_off")
    tid = (10).to_bytes(16, "big")
    conflict_a = _proto_span(
        (11).to_bytes(16, "big"),
        b"\x13" * 8,
        # "x" as a leaf and "x.y" under it can't both exist -> parse failure.
        attrs={"x": "leaf", "x.y": "nested"},
    )
    conflict_b = _proto_span(
        (12).to_bytes(16, "big"), b"\x14" * 8, attrs={"y": "leaf", "y.z": "nested"}
    )
    res = _export(
        ch_server,
        project_id,
        _proto_span(tid, b"\x11" * 8),
        conflict_a,
        _proto_span(tid, b"\x12" * 8, parent_span_id=b"\x11" * 8),
        conflict_b,
    )
    assert res.accepted_spans == 2
    assert res.rejected_spans == 2
    assert res.error_message == "; ".join(
        _conflict_error(span) for span in (conflict_a, conflict_b)
    )
    assert len(_stored_spans(ch_server, project_id)) == 2
    # Disabled sampler emits nothing at all.
    assert sampler_metrics == {
        "seen": [],
        "parse_failures": [],
        "evals_kept": [],
        "dropped": [],
    }


@pytest.mark.flaky(reruns=3)
def test_rate_zero_drops_non_eval_trace_whole(
    ch_server, sampler_metrics: dict[str, list], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", "0.0")
    project_id = make_project_id("spans_sampling_drop")
    tid = (20).to_bytes(16, "big")
    res = _export(
        ch_server,
        project_id,
        _proto_span(tid, b"\x21" * 8),
        _proto_span(tid, b"\x22" * 8, parent_span_id=b"\x21" * 8),
    )
    # Dropped spans still count as accepted: the client sees an ordinary
    # success, mirroring the calls model.
    assert res.accepted_spans == 2
    assert res.rejected_spans == 0
    assert _stored_spans(ch_server, project_id) == []
    assert [(c, d) for c, _, d in sampler_metrics["dropped"]] == [(2, False)]
    assert all(size > 0 for _, size, _ in sampler_metrics["dropped"])


@pytest.mark.flaky(reruns=3)
def test_eval_marked_trace_kept_whole_at_rate_zero(
    ch_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One marked span protects the whole trace -- including unmarked
    children in the same request, and regardless of which client set the
    marker (the same rule is the documented opt-in for foreign OTel).
    """
    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", "0.0")
    project_id = make_project_id("spans_sampling_eval")
    tid = (30).to_bytes(16, "big")
    res = _export(
        ch_server,
        project_id,
        _proto_span(tid, b"\x31" * 8, attrs={EVAL_MARKER_ATTR: "pas-3"}),
        _proto_span(tid, b"\x32" * 8, parent_span_id=b"\x31" * 8),
    )
    assert res.accepted_spans == 2
    assert len(_stored_spans(ch_server, project_id)) == 2


@pytest.mark.flaky(reruns=3)
def test_dry_run_keeps_everything_and_stamps_nothing(
    ch_server, sampler_metrics: dict[str, list], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", "0.0")
    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_DRY_RUN", "true")
    project_id = make_project_id("spans_sampling_dryrun")
    tid = (40).to_bytes(16, "big")
    res = _export(ch_server, project_id, _proto_span(tid, b"\x41" * 8))
    assert res.accepted_spans == 1
    stored = _stored_spans(ch_server, project_id)
    assert len(stored) == 1
    # A dry-run keep is a kept-whole span: no rate stamp, or reconstructed
    # totals would double-count the hash winners.
    assert stored[0].custom_attrs_float == {}
    assert [(c, d) for c, _, d in sampler_metrics["dropped"]] == [(1, True)]


@pytest.mark.flaky(reruns=3)
def test_hash_kept_trace_is_stamped_with_rate(
    ch_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    rate = 0.5
    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", str(rate))
    project_id = make_project_id("spans_sampling_stamp")
    tid = _tid_with_verdict(rate, kept=True)
    res = _export(
        ch_server,
        project_id,
        # A client-supplied float under the stamp key is overwritten on a
        # genuine keep; a *string* "0.5" lands in the string map and cannot
        # touch the float map the weighting consumer reads.
        _proto_span(tid, b"\x51" * 8, attrs={STAMP_ATTR: 0.9}),
        _proto_span(
            tid, b"\x52" * 8, parent_span_id=b"\x51" * 8, attrs={STAMP_ATTR: "0.5"}
        ),
    )
    assert res.accepted_spans == 2
    stored = sorted(_stored_spans(ch_server, project_id), key=lambda s: s.span_id)
    assert len(stored) == 2
    for span in stored:
        assert span.custom_attrs_float == {STAMP_ATTR: rate}
    assert stored[1].custom_attrs_string[STAMP_ATTR] == "0.5"


@pytest.mark.flaky(reruns=3)
def test_mixed_request_drops_selectively(
    ch_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    rate = 0.5
    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", str(rate))
    project_id = make_project_id("spans_sampling_mixed")
    kept_tid = _tid_with_verdict(rate, kept=True)
    dropped_tid = _tid_with_verdict(rate, kept=False)
    conflict = _proto_span(
        (60).to_bytes(16, "big"), b"\x63" * 8, attrs={"x": "leaf", "x.y": "nested"}
    )
    res = _export(
        ch_server,
        project_id,
        _proto_span(kept_tid, b"\x61" * 8),
        _proto_span(dropped_tid, b"\x62" * 8),
        conflict,
    )
    # Parse failures stay rejected in the sampled path exactly as today.
    assert res.accepted_spans == 2
    assert res.rejected_spans == 1
    assert res.error_message == _conflict_error(conflict)
    stored = _stored_spans(ch_server, project_id)
    assert [s.trace_id for s in stored] == [kept_tid.hex()]


@pytest.mark.flaky(reruns=3)
def test_unusable_trace_ids_fail_open(
    ch_server, sampler_metrics: dict[str, list], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", "0.0")
    project_id = make_project_id("spans_sampling_failopen")
    res = _export(
        ch_server,
        project_id,
        _proto_span(b"", b"\x71" * 8),  # empty id
        _proto_span(b"\xab" * 15, b"\x72" * 8),  # 15-byte id
        _proto_span(b"\xab" * 17, b"\x73" * 8),  # 17-byte id
        _proto_span(b"\x00" * 16, b"\x74" * 8),  # OTel-invalid zero id
    )
    assert res.accepted_spans == 4
    assert len(_stored_spans(ch_server, project_id)) == 4
    assert sampler_metrics["parse_failures"] == [4]
    assert sampler_metrics["dropped"] == []


@pytest.mark.flaky(reruns=3)
def test_dropped_trace_writes_no_content_files(
    ch_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deciding before blob-strip means a dropped trace leaves no orphaned
    Content files behind.
    """
    b64 = base64.b64encode(b"x" * (AUTO_CONVERSION_MIN_SIZE + 100)).decode("ascii")
    messages_json = json.dumps(
        [
            {
                "role": "user",
                "parts": [
                    {"type": "text", "content": "describe"},
                    {"type": "image", "url": f"data:image/png;base64,{b64}"},
                ],
            }
        ]
    )
    attrs = {"gen_ai.input.messages": messages_json}

    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", "0.0")
    dropped_project = make_project_id("spans_sampling_nofiles")
    _export(
        ch_server,
        dropped_project,
        _proto_span((80).to_bytes(16, "big"), b"\x81" * 8, attrs=attrs),
    )
    dropped_stats = ch_server.files_stats(tsi.FilesStatsReq(project_id=dropped_project))
    assert dropped_stats.total_size_bytes == 0

    # Control: the same payload with the sampler off does write a Content file.
    monkeypatch.delenv("WEAVE_INGEST_SAMPLE_RATE", raising=False)
    kept_project = make_project_id("spans_sampling_files")
    _export(
        ch_server,
        kept_project,
        _proto_span((81).to_bytes(16, "big"), b"\x82" * 8, attrs=attrs),
    )
    kept_stats = ch_server.files_stats(tsi.FilesStatsReq(project_id=kept_project))
    assert kept_stats.total_size_bytes > 0


@pytest.mark.flaky(reruns=3)
def test_dropped_trace_emits_no_scoring_event(
    ch_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drop = not stored AND not scored: the Kafka emit is fed by the same
    filtered rows, so a dropped turn root never reaches the scoring worker.
    """
    monkeypatch.setattr(environment, "wf_enable_online_eval", lambda: True)
    monkeypatch.setattr(environment, "wf_enable_agent_scoring", lambda: True)
    producer = MagicMock()
    monkeypatch.setattr(ch_server, "_kafka_producer", producer)
    monkeypatch.setenv("WEAVE_INGEST_SAMPLE_RATE", "0.0")

    dropped_project = make_project_id("spans_sampling_nokafka")
    _export(
        ch_server,
        dropped_project,
        _proto_span((90).to_bytes(16, "big"), b"\x91" * 8),
    )
    producer.produce_score_agent_spans.assert_not_called()

    # A kept turn root (eval carve-out) still emits exactly one event.
    kept_project = make_project_id("spans_sampling_kafka")
    _export(
        ch_server,
        kept_project,
        _proto_span(
            (91).to_bytes(16, "big"), b"\x92" * 8, attrs={EVAL_MARKER_ATTR: "pas-4"}
        ),
    )
    producer.produce_score_agent_spans.assert_called_once()
