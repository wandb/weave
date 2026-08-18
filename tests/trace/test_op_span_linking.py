"""Tests for recording the invoking OTel span on the call it triggered."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.sdk.trace.sampling import Decision, StaticSampler
from opentelemetry.trace import NonRecordingSpan, Span, SpanContext, TraceFlags

import weave
from weave.trace.call import Call
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server import tracing as server_tracing
from weave.trace_server.constants import INVOKING_SPAN_ATTR_KEY

FORGED = {"trace_id": "f" * 32, "span_id": "f" * 16}


class _ZeroIdGenerator(IdGenerator):
    """Hands out the all-zero identity, which is sampled but not valid."""

    def generate_span_id(self) -> int:
        return 0

    def generate_trace_id(self) -> int:
        return 0


class _BridgeSpan(NonRecordingSpan):
    """Live and sampled, but not an SDK span — the shape the DD bridge hands out."""

    def is_recording(self) -> bool:
        return True


class _BridgeTracer:
    """Minimal tracer yielding `_BridgeSpan`, standing in for a bridged provider."""

    @contextmanager
    def start_as_current_span(self, name: str, *args, **kwargs) -> Iterator[Span]:
        span = _BridgeSpan(
            SpanContext(
                trace_id=0x0F1E2D3C4B5A69788796A5B4C3D2E1F0,
                span_id=0xA1B2C3D4E5F60718,
                is_remote=False,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
        )
        with otel_trace.use_span(span, end_on_exit=False):
            yield span


@pytest.fixture
def install_otel_spans(monkeypatch: pytest.MonkeyPatch):
    """Install an isolated OTel provider and return its span exporter.

    A factory rather than a plain fixture because the sampler and id generator
    are chosen at ``TracerProvider`` construction. Isolation is required rather
    than convenient: on a shared provider the trace server's own spans are
    current while a query stream is consumed, so these assertions would depend
    on unrelated server work.
    """
    providers = []

    def install(**provider_kwargs) -> InMemorySpanExporter:
        exporter = InMemorySpanExporter()
        provider = SDKTracerProvider(**provider_kwargs)
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
        providers.append(provider)
        return exporter

    yield install

    for provider in providers:
        provider.shutdown()


def _invoking_span(call: Call) -> dict | None:
    return call.attributes["weave"].get(INVOKING_SPAN_ATTR_KEY)


def _expected_invoking_span(span: otel_trace.Span) -> dict[str, str]:
    ctx = span.get_span_context()
    return {
        "trace_id": otel_trace.format_trace_id(ctx.trace_id),
        "span_id": otel_trace.format_span_id(ctx.span_id),
    }


def test_written_for_op_inside_span(client, install_otel_spans):
    install_otel_spans()
    tracer = otel_trace.get_tracer("test")

    @weave.op
    def lookup(query: str) -> str:
        return query

    with tracer.start_as_current_span("execute_tool lookup") as span:
        with weave.attributes({"env": "test"}):
            _, call = lookup.call("papers")
        expected = _expected_invoking_span(span)

    assert _invoking_span(call) == expected
    assert call.attributes["env"] == "test"


def test_absent_outside_any_span(client, install_otel_spans):
    install_otel_spans()

    @weave.op
    def lookup(query: str) -> str:
        return query

    _, call = lookup.call("papers")

    assert INVOKING_SPAN_ATTR_KEY not in call.attributes["weave"]


def test_nested_ops_share_one_invoking_span(client, install_otel_spans):
    """Every call started inside the span carries it, not just the outermost.

    Skipping the write when the parent call already carries the same value
    would mark every other level (root yes, child no, grandchild yes), because
    such a check reads the parent's *recorded* state and the parent may itself
    have skipped the write.
    """
    install_otel_spans()
    tracer = otel_trace.get_tracer("test")
    nested_calls: list[Call] = []

    @weave.op
    def inner(x: int) -> int:
        nested_calls.append(weave.require_current_call())
        return x

    @weave.op
    def middle(x: int) -> int:
        nested_calls.append(weave.require_current_call())
        return inner(x)

    @weave.op
    def outer(x: int) -> int:
        return middle(x)

    with tracer.start_as_current_span("execute_tool outer") as span:
        _, outer_call = outer.call(1)
        expected = _expected_invoking_span(span)

    assert _invoking_span(outer_call) == expected
    assert [_invoking_span(c) for c in nested_calls] == [expected, expected]


def test_absent_for_record_only_span(client, install_otel_spans):
    """RECORD_ONLY records the span but never exports it, so nothing resolves."""
    install_otel_spans(sampler=StaticSampler(Decision.RECORD_ONLY))
    tracer = otel_trace.get_tracer("test")

    @weave.op
    def lookup(query: str) -> str:
        return query

    with tracer.start_as_current_span("execute_tool lookup") as span:
        assert span.is_recording()
        assert not span.get_span_context().trace_flags.sampled
        _, call = lookup.call("papers")

    assert INVOKING_SPAN_ATTR_KEY not in call.attributes["weave"]


def test_absent_for_all_zero_span_identity(client, install_otel_spans):
    """A custom id generator can hand out an identity that is sampled but invalid.

    All-zero ids would match every other all-zero pair in the project, so the
    reference would resolve to the wrong calls rather than to none.
    """
    install_otel_spans(id_generator=_ZeroIdGenerator())
    tracer = otel_trace.get_tracer("test")

    @weave.op
    def lookup(query: str) -> str:
        return query

    with tracer.start_as_current_span("execute_tool lookup") as span:
        ctx = span.get_span_context()
        assert span.is_recording()
        assert ctx.trace_flags.sampled
        assert not ctx.is_valid
        _, call = lookup.call("papers")

    assert INVOKING_SPAN_ATTR_KEY not in call.attributes["weave"]


def test_absent_when_span_already_ended(client, install_otel_spans):
    install_otel_spans()
    tracer = otel_trace.get_tracer("test")

    @weave.op
    def lookup(query: str) -> str:
        return query

    span = tracer.start_span("execute_tool lookup")
    with otel_trace.use_span(span, end_on_exit=False):
        span.end()
        _, call = lookup.call("papers")

    assert INVOKING_SPAN_ATTR_KEY not in call.attributes["weave"]


def test_absent_inside_a_weave_server_span(client, install_otel_spans):
    """A trace server span is not an agent span, and in-process it is current.

    Driven through the real `@traced` decorator: the recognition depends on
    the server marking its own context, so testing the mechanism rather than a
    copy of it is what keeps the two sides from drifting apart.
    """
    install_otel_spans()

    @weave.op
    def lookup(query: str) -> str:
        return query

    @server_tracing.traced(name="clickhouse_trace_server_batched.calls_query_stream")
    def server_frame() -> Call:
        return lookup.call("papers")[1]

    call = server_frame()

    assert INVOKING_SPAN_ATTR_KEY not in call.attributes["weave"]


def test_absent_inside_a_server_span_that_is_not_an_sdk_span(
    client, install_otel_spans, monkeypatch: pytest.MonkeyPatch
):
    """Recognising our own server frame must not depend on the span's type.

    Under the OTel→DD bridge the current span is not an SDK span and carries
    no instrumentation scope, so anything read off the span object would pass
    straight through exactly where this matters. `tracing` documents `_tracer`
    as the seam tests swap.
    """
    install_otel_spans()

    @weave.op
    def lookup(query: str) -> str:
        return query

    @server_tracing.traced(name="evaluate_model_worker.evaluate_model.run_evaluation")
    def server_frame() -> tuple[Call, otel_trace.Span]:
        return lookup.call("papers")[1], otel_trace.get_current_span()

    monkeypatch.setattr(server_tracing, "_tracer", _BridgeTracer())
    call, span = server_frame()

    assert not hasattr(span, "instrumentation_scope")
    assert INVOKING_SPAN_ATTR_KEY not in call.attributes["weave"]


def test_written_for_an_agent_span_inside_a_server_span(client, install_otel_spans):
    """A hosted evaluation runs an agent inside a `@traced` frame.

    Suppressing on "somewhere inside a server frame" would lose the link in
    exactly the case it is most wanted, so the check compares against the
    server's own span rather than a flag.
    """
    install_otel_spans()
    tracer = otel_trace.get_tracer("test")

    @weave.op
    def lookup(query: str) -> str:
        return query

    @server_tracing.traced(name="evaluate_model_worker.evaluate_model.run_evaluation")
    def server_frame() -> tuple[Call, dict[str, str]]:
        with tracer.start_as_current_span("execute_tool lookup") as span:
            return lookup.call("papers")[1], _expected_invoking_span(span)

    call, expected = server_frame()

    assert _invoking_span(call) == expected


def test_caller_supplied_value_is_never_kept(client, install_otel_spans):
    """The key is ours to write, so a caller's value loses either way.

    ``create_call`` is the seam that accepts one: on the ``@weave.op`` path the
    SDK replaces the whole ``weave`` sub-dict, so nothing a caller passes there
    ever arrives.
    """
    install_otel_spans()
    tracer = otel_trace.get_tracer("test")
    attributes = {"weave": {INVOKING_SPAN_ATTR_KEY: FORGED}}

    with tracer.start_as_current_span("execute_tool lookup") as span:
        inside = client.create_call(
            "inside", {}, attributes=attributes, use_stack=False
        )
        expected = _expected_invoking_span(span)
    outside = client.create_call("outside", {}, attributes=attributes, use_stack=False)

    assert _invoking_span(inside) == expected
    assert INVOKING_SPAN_ATTR_KEY not in outside.attributes["weave"]


def test_bare_thread_loses_it_but_weave_executor_keeps_it(client, install_otel_spans):
    """OTel context does not cross a raw thread; ``weave.ThreadPoolExecutor`` copies it."""
    install_otel_spans()
    tracer = otel_trace.get_tracer("test")

    @weave.op
    def lookup(query: str) -> str:
        return query

    with tracer.start_as_current_span("execute_tool lookup") as span:
        bare_calls: list[Call] = []
        thread = threading.Thread(
            target=lambda: bare_calls.append(lookup.call("papers")[1])
        )
        thread.start()
        thread.join()

        with weave.ThreadPoolExecutor(max_workers=1) as executor:
            copied_call = executor.submit(lambda: lookup.call("papers")[1]).result()

        expected = _expected_invoking_span(span)

    assert INVOKING_SPAN_ATTR_KEY not in bare_calls[0].attributes["weave"]
    assert _invoking_span(copied_call) == expected


def test_points_at_the_conversation_sdk_tool_span(client, install_otel_spans):
    """``weave.Tool`` opens ``execute_tool <name>`` and makes it current."""
    exporter = install_otel_spans()

    @weave.op
    def lookup(query: str) -> str:
        return query

    with weave.Tool(name="lookup"):
        _, call = lookup.call("papers")

    tool_span = next(
        s for s in exporter.get_finished_spans() if s.name == "execute_tool lookup"
    )

    assert _invoking_span(call) == _expected_invoking_span(tool_span)


def test_survives_the_round_trip_and_is_queryable(client, install_otel_spans):
    """It reaches the stored column and the pair filter finds that exact call.

    A typo in the attribute path returns zero rows rather than an error, which
    is indistinguishable from "it was never written", so this pins the id.
    """
    install_otel_spans()
    tracer = otel_trace.get_tracer("test")

    @weave.op
    def lookup(query: str) -> str:
        return query

    with tracer.start_as_current_span("execute_tool lookup") as span:
        _, call = lookup.call("papers")
        expected = _expected_invoking_span(span)

    client.flush()

    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                query=tsi.Query.model_validate(
                    {
                        "$expr": {
                            "$and": [
                                {
                                    "$eq": [
                                        {
                                            "$getField": f"attributes.weave.{INVOKING_SPAN_ATTR_KEY}.trace_id"
                                        },
                                        {"$literal": expected["trace_id"]},
                                    ]
                                },
                                {
                                    "$eq": [
                                        {
                                            "$getField": f"attributes.weave.{INVOKING_SPAN_ATTR_KEY}.span_id"
                                        },
                                        {"$literal": expected["span_id"]},
                                    ]
                                },
                            ]
                        }
                    }
                ),
            )
        )
    )

    assert [c.id for c in calls] == [call.id]
    assert calls[0].attributes["weave"][INVOKING_SPAN_ATTR_KEY] == expected
