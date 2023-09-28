# Trace Weave engine with Datadog
#
# There are four trace modes:
#   DD_ENV & !WEAVE_TRACE_STREAM: log to datadog only
#   [experimental] DD_ENV & WEAVE_TRACE_STREAM: mirror datadog spans to a W&B StreamTable
#     this is good because it uses all the datadog instrumentation
#   [experimental] !DD_ENV & WEAVE_TRACE_STREAM: log trace tree traces to a W&B StreamTable
#     only captures trace calls, not other library instrumentation as added by datadog
#   None: DummyTrace that does nothing


import os
import typing
import contextvars
import multiprocessing
import logging
import time
import json
import dataclasses

from . import logs
from . import stream_data_interfaces


# Thanks co-pilot!
class DummySpan:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.log_indent_token = None

    def __enter__(self):
        logging.debug("-> %s", self.args[0])
        self.log_indent_token = logs.increment_indent()
        return self

    def __exit__(self, *args, **kwargs):
        logs.reset_indent(self.log_indent_token)
        logging.debug("<- %s", self.args[0])

    def set_tag(self, *args, **kwargs):
        pass

    def set_meta(self, *args, **kwargs):
        pass

    def finish(self, *args, **kwargs):
        pass


class TraceContext:
    def __getstate__(self) -> dict:
        return {}

    def __setstate__(self, state: dict) -> None:
        pass


class ContextProvider:
    def activate(self, context: TraceContext) -> None:
        pass


class DummyTrace:
    def trace(self, *args, **kwargs):
        return DummySpan(*args)

    @property
    def context_provider(self) -> ContextProvider:
        return ContextProvider()

    def current_trace_context(self) -> typing.Optional[TraceContext]:
        return None

    def current_span(self):
        return None

    def current_root_span(self):
        return None


_weave_trace_span: contextvars.ContextVar[
    typing.Optional["WeaveTraceSpan"]
] = contextvars.ContextVar("_weave_trace_span", default=None)


_weave_trace_stream = None


def weave_trace_stream():
    global _weave_trace_stream
    if _weave_trace_stream is None:
        from weave.wandb_interface.wandb_stream_table import StreamTable

        _weave_trace_stream = StreamTable(os.getenv("WEAVE_TRACE_STREAM"))
    return _weave_trace_stream


def span_count(span):
    if span.child_spans is None:
        return 1
    return 1 + sum([span_count(child) for child in span.child_spans])


class WeaveTraceSpan:
    def __init__(self, name):
        from .ops_domain import trace_tree

        self.log_indent_token = None
        self._token = None
        self.span = trace_tree.Span(_name=name)
        self._parent = None

    def total_span_count(self):
        return span_count(self.span)

    def __enter__(self):
        parent = _weave_trace_span.get()
        if parent is not None:
            if parent.span.child_spans is None:
                parent.span.child_spans = []
            parent.span.child_spans.append(self.span)
            self._parent = parent

        self._token = _weave_trace_span.set(self)
        self.span.start_time_ms = int(time.time() * 1000)
        return self

    def __exit__(self, *args, **kwargs):
        self.span.end_time_ms = int(time.time() * 1000)
        _weave_trace_span.reset(self._token)

        from .ops_domain import trace_tree

        tt = trace_tree.WBTraceTree(json.dumps(dataclasses.asdict(self.span)))
        tags = self.attributes.get("tags", {})
        if _weave_trace_span.get() is None:
            weave_trace_stream().log(
                {
                    "span_count": self.total_span_count(),
                    "duration_ms": self.span.end_time_ms - self.span.start_time_ms,
                    **tags,
                    "trace": tt,
                }
            )

    @property
    def attributes(self):
        if self.span.attributes is None:
            self.span.attributes = {}
        return self.span.attributes

    def set_tag(self, key, val):
        if "tags" not in self.attributes:
            self.attributes["tags"] = {}
        self.attributes["tags"][key] = val

    def set_meta(self, key, val):
        if "metadata" not in self.attributes:
            self.attributes["metadata"] = {}
        self.attributes["metadata"][key] = val

    def finish(self, *args, **kwargs):
        pass


class WeaveTrace:
    def __init__(self):
        self._stream_table = None

    def trace(self, name, *args, **kwargs):
        return WeaveTraceSpan(name, *args)

    @property
    def context_provider(self) -> ContextProvider:
        return ContextProvider()

    def current_trace_context(self) -> typing.Optional[TraceContext]:
        return None

    def current_span(self):
        return _weave_trace_span.get()

    def current_root_span(self):
        cur_span = _weave_trace_span.get()
        while cur_span is not None and cur_span._parent is not None:
            cur_span = cur_span._parent
        return cur_span


def dd_span_to_weave_span(dd_span) -> stream_data_interfaces.TraceSpanDict:
    # Use '' for None, currently history2 doesn't read None columns from
    # the liveset correctly.
    parent_id = ""
    if dd_span.parent_id is not None:
        parent_id = str(dd_span.parent_id)

    return {
        "name": dd_span.name,
        "start_time_s": dd_span.start_ns / 1e9,
        "end_time_s": (dd_span.start_ns + dd_span.duration_ns) / 1e9,
        "attributes": dd_span.get_tags(),
        "trace_id": str(dd_span.trace_id),
        "span_id": str(dd_span.span_id),
        "parent_id": parent_id,
        "status_code": "UNSET",
        "inputs": None,
        "output": None,
        "summary": None,
        "exception": None,
    }


def send_proc(queue):
    while True:
        spans = queue.get()
        if spans is None:
            break
        trace_stream = weave_trace_stream()
        if trace_stream is not None:
            for span in spans:
                trace_stream.log(span)


# A DataDog writer that sends spans to W&B as a StreamTable.
# We have to use a separate process for writing the stream, otherwise things hang.
# My guess is this is because logging to StreamTable uses gql, which is wrapped
# by datadog, so we have some kind of re-entrancy/deadlock. Putting in a separate
# process fixes.
class WeaveWriter:
    def __init__(self, orig_writer):
        self._orig_writer = orig_writer
        self._queue = multiprocessing.Queue()
        self._proc = multiprocessing.Process(
            target=send_proc, args=(self._queue,), daemon=True
        )

    def recreate(self):
        return WeaveWriter(self._orig_writer.recreate())

    def stop(self, timeout=None):
        self._orig_writer.stop(timeout)

    def _ensure_started(self):
        if not self._proc.is_alive():
            self._proc.start()

    def write(self, spans):
        if len(spans) == 1:
            return
        self._ensure_started()
        self._queue.put([dd_span_to_weave_span(s) for s in spans])
        self._orig_writer.write(spans)

    def flush_queue(self):
        self._orig_writer.flush_queue()


def tracer():
    if os.getenv("DD_ENV"):
        from ddtrace import tracer as ddtrace_tracer

        if os.getenv("WEAVE_TRACE_STREAM"):
            # In DataDog mode, if WEAVE_TRACE_STREAM is set, experimentally
            # mirror DataDog trace info to W&B.
            # In this mode we log a table of spans, as opposed to traces.
            if not isinstance(ddtrace_tracer._writer, WeaveWriter):
                ddtrace_tracer._writer = WeaveWriter(ddtrace_tracer._writer)
                from ddtrace.internal.processor.trace import SpanAggregator

                span_agg = ddtrace_tracer._span_processors[-1]
                if not isinstance(span_agg, SpanAggregator):
                    raise ValueError("unable to patch ddtrace tracer")
                span_agg._writer = ddtrace_tracer._writer

        return ddtrace_tracer
    elif os.getenv("WEAVE_TRACE_STREAM"):
        # Without DataDog, WEAVE_TRACE_STREAM tells us to log any trace calls as a trace tree
        return WeaveTrace()
    else:
        return DummyTrace()


def new_trace_context() -> typing.Optional[TraceContext]:
    if os.getenv("DD_ENV"):
        from ddtrace import context as ddtrace_context

        return ddtrace_context.Context()  # type: ignore
    else:
        return None


class DummyStatsd:
    def __init__(self, *args, **kwargs):
        pass

    def increment(self, *args, **kwargs):
        pass

    def decrement(self, *args, **kwargs):
        pass

    def gauge(self, *args, **kwargs):
        pass

    def flush(self, *args, **kwargs):
        pass


_STATSD = None


def _initialize_statsd():
    if os.getenv("DD_ENV"):
        from datadog import initialize, statsd

        initialize(statsd_disable_buffering=False)
        return statsd
    else:
        return DummyStatsd()


def statsd():
    global _STATSD
    if _STATSD is None:
        _STATSD = _initialize_statsd()

    return _STATSD


def datadog_is_enabled():
    return os.getenv("DD_ENV")
