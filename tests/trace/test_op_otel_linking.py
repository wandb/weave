"""Tests for op linkage stamping via OpLinkSpanProcessor."""

from __future__ import annotations

import asyncio
import threading

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import SpanLimits
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import weave
from weave import Evaluation
from weave.conversation import start_conversation
from weave.conversation.types import Message
from weave.evaluation.otel_eval_linker import EvalLinkSpanProcessor
from weave.shared.otel_span_attrs import (
    PARENT_CALL_ID_SPAN_ATTR,
    PARENT_CALL_TRACE_ID_SPAN_ATTR,
)
from weave.trace.otel_op_linker import OpLinkSpanProcessor
from weave.trace_server import constants


@pytest.fixture
def otel_setup(monkeypatch: pytest.MonkeyPatch):
    """Install an isolated OTel provider carrying both link processors.

    OTel allows set_tracer_provider once per process, so we build the same
    processor stack weave.init() builds onto a temporary provider instead of
    mutating whatever provider is already active.
    """
    exporter = InMemorySpanExporter()

    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    provider.add_span_processor(EvalLinkSpanProcessor())
    provider.add_span_processor(OpLinkSpanProcessor())
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)

    yield exporter

    provider.shutdown()


def _emit_span(name: str = "work") -> None:
    """Create and end a plain OTel span through the global tracer."""
    otel_trace.get_tracer("test").start_span(name).end()


def _emit_wide_span(name: str, extra_attributes: int) -> None:
    """Emit a span carrying `extra_attributes` attributes of its own."""
    span = otel_trace.get_tracer("test").start_span(name)
    for i in range(extra_attributes):
        span.set_attribute(f"custom.{i}", i)
    span.end()


def _attrs_by_span_name(exporter: InMemorySpanExporter) -> dict[str, dict]:
    return {span.name: dict(span.attributes) for span in exporter.get_finished_spans()}


def test_span_inside_op_carries_call_ids(client, otel_setup):
    """The core of the feature: a span emitted under an op gets both ids."""

    @weave.op
    def orchestrate() -> str:
        _emit_span("agent_work")
        return "done"

    orchestrate()
    client.flush()
    call = next(iter(orchestrate.calls()))

    attrs = _attrs_by_span_name(otel_setup)["agent_work"]
    assert attrs[PARENT_CALL_ID_SPAN_ATTR] == call.id
    assert attrs[PARENT_CALL_TRACE_ID_SPAN_ATTR] == call.trace_id


def test_span_outside_op_carries_no_link(client, otel_setup):
    """No call on the stack means no link, not an empty-string link."""
    _emit_span("standalone")

    attrs = _attrs_by_span_name(otel_setup)["standalone"]
    assert PARENT_CALL_ID_SPAN_ATTR not in attrs
    assert PARENT_CALL_TRACE_ID_SPAN_ATTR not in attrs


def test_subtree_spans_carry_innermost_call(client, otel_setup):
    """Each span links to the call that was innermost when it started.

    The whole subtree is stamped, matching the eval processor; a nested op
    takes over the spans started inside it.
    """

    @weave.op
    def inner_op() -> None:
        _emit_span("grandchild")

    @weave.op
    def outer_op() -> None:
        tracer = otel_trace.get_tracer("test")
        with tracer.start_as_current_span("root"):
            with tracer.start_as_current_span("child"):
                inner_op()

    outer_op()
    client.flush()
    outer = next(iter(outer_op.calls()))
    inner = next(iter(inner_op.calls()))

    attrs = _attrs_by_span_name(otel_setup)
    assert attrs["root"][PARENT_CALL_ID_SPAN_ATTR] == outer.id
    assert attrs["child"][PARENT_CALL_ID_SPAN_ATTR] == outer.id
    assert attrs["grandchild"][PARENT_CALL_ID_SPAN_ATTR] == inner.id
    assert inner.id != outer.id


def test_conversation_sdk_spans_carry_call(client, otel_setup):
    """The Conversation SDK is the span source behind claude_agent_sdk too."""

    @weave.op
    def orchestrate() -> None:
        with start_conversation(
            agent_name="weather-bot", conversation_id="conversation-1"
        ) as conversation:
            with conversation.start_turn() as turn:
                with turn.llm(model="gpt-4o") as llm:
                    llm.output("Sunny")

    orchestrate()
    client.flush()
    call = next(iter(orchestrate.calls()))

    attrs = _attrs_by_span_name(otel_setup)
    assert set(attrs) == {"invoke_agent weather-bot", "chat gpt-4o"}
    links = {
        (a[PARENT_CALL_ID_SPAN_ATTR], a[PARENT_CALL_TRACE_ID_SPAN_ATTR])
        for a in attrs.values()
    }
    assert links == {(call.id, call.trace_id)}


def test_log_turn_links_only_inside_op(client, otel_setup):
    """The batch path reads the call stack even though it never writes to it.

    ``log_turn`` emits through ``_emit_span_now``, which deliberately does not
    make its span current, so the link follows whoever called it: present
    inside an op, absent from a queue worker outside one.
    """

    @weave.op
    def orchestrate() -> None:
        weave.log_turn(
            conversation_id="conversation-in-op",
            agent_name="inside",
            messages=[Message(role="user", content="hi")],
        )

    orchestrate()
    weave.log_turn(
        conversation_id="conversation-out-of-op",
        agent_name="outside",
        messages=[Message(role="user", content="hi")],
    )
    client.flush()
    call = next(iter(orchestrate.calls()))

    attrs = _attrs_by_span_name(otel_setup)
    inside = attrs["invoke_agent inside"]
    assert inside[PARENT_CALL_ID_SPAN_ATTR] == call.id
    assert inside[PARENT_CALL_TRACE_ID_SPAN_ATTR] == call.trace_id
    assert PARENT_CALL_ID_SPAN_ATTR not in attrs["invoke_agent outside"]


@pytest.mark.asyncio
async def test_eval_spans_carry_both_links(client, otel_setup):
    """The two processors are independent — an eval span gets both stampings."""

    @weave.op
    async def model_predict(input: str) -> str:
        _emit_span("chat")
        return input

    evaluation = Evaluation(dataset=[{"input": "1 + 1"}], scorers=[])
    await evaluation.evaluate(model_predict)
    client.flush()
    call = next(iter(model_predict.calls()))

    attrs = _attrs_by_span_name(otel_setup)["chat"]
    assert attrs[PARENT_CALL_ID_SPAN_ATTR] == call.id
    assert attrs[PARENT_CALL_TRACE_ID_SPAN_ATTR] == call.trace_id
    assert attrs[constants.EVAL_PROJECT_ID_SPAN_ATTR] == client.project_id
    assert attrs[constants.EVAL_KIND_SPAN_ATTR] == "standard"


def test_link_survives_attribute_limit_and_drops_past_it(client, otel_setup):
    """Both ids are written at span start, so they are the first attributes
    evicted once a span exceeds OTel's count limit. Pins both sides of that
    boundary, because a wide span silently losing the link is the one failure
    mode a caller cannot see.
    """
    limit = SpanLimits().max_span_attributes
    assert limit is not None

    @weave.op
    def orchestrate() -> None:
        _emit_wide_span("at_limit", limit - 2)
        _emit_wide_span("over_limit", limit)

    orchestrate()
    client.flush()
    call = next(iter(orchestrate.calls()))

    attrs = _attrs_by_span_name(otel_setup)
    assert attrs["at_limit"][PARENT_CALL_ID_SPAN_ATTR] == call.id
    assert attrs["at_limit"][PARENT_CALL_TRACE_ID_SPAN_ATTR] == call.trace_id
    assert PARENT_CALL_ID_SPAN_ATTR not in attrs["over_limit"]
    assert PARENT_CALL_TRACE_ID_SPAN_ATTR not in attrs["over_limit"]


def test_bare_thread_drops_link_weave_pool_keeps_it(client, otel_setup):
    """The call stack is a ContextVar, so a bare thread starts without it.

    This is the mechanism behind every source that cannot be linked: a span
    created on a library-owned thread (ADK's sync Runner.run, the realtime
    FIFO timer) cannot see the call.
    """

    @weave.op
    def orchestrate() -> None:
        thread = threading.Thread(target=_emit_span, args=("bare_thread",))
        thread.start()
        thread.join()
        with weave.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(_emit_span, "weave_pool").result()

    orchestrate()
    client.flush()
    call = next(iter(orchestrate.calls()))

    attrs = _attrs_by_span_name(otel_setup)
    assert PARENT_CALL_ID_SPAN_ATTR not in attrs["bare_thread"]
    assert attrs["weave_pool"][PARENT_CALL_ID_SPAN_ATTR] == call.id


@pytest.mark.asyncio
async def test_asyncio_task_carries_call(client, otel_setup):
    """asyncio.Task copies the context, unlike a bare thread."""

    async def emit() -> None:
        _emit_span("task")

    @weave.op
    async def orchestrate() -> None:
        await asyncio.create_task(emit())

    await orchestrate()
    client.flush()
    call = next(iter(orchestrate.calls()))

    attrs = _attrs_by_span_name(otel_setup)["task"]
    assert attrs[PARENT_CALL_ID_SPAN_ATTR] == call.id


@pytest.mark.asyncio
async def test_task_outliving_op_links_finished_call(client, otel_setup):
    """A task holds a copy of the call stack, so it can stamp a call that has
    already finished. The link is correct; readers must tolerate it pointing
    at a completed call.
    """
    tasks: list[asyncio.Task] = []
    released = asyncio.Event()

    async def emit_when_released() -> None:
        await released.wait()
        _emit_span("after_op")

    @weave.op
    async def orchestrate() -> None:
        tasks.append(asyncio.create_task(emit_when_released()))

    await orchestrate()
    released.set()
    await tasks[0]
    client.flush()
    call = next(iter(orchestrate.calls()))

    attrs = _attrs_by_span_name(otel_setup)["after_op"]
    assert attrs[PARENT_CALL_ID_SPAN_ATTR] == call.id
