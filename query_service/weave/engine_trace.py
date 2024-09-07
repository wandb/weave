# Trace Weave engine with Datadog
#
# There are four trace modes:
#   DD_ENV & !WEAVE_TRACE_STREAM: log to datadog only
#   [experimental] DD_ENV & WEAVE_TRACE_STREAM: mirror datadog spans to a W&B StreamTable
#     this is good because it uses all the datadog instrumentation
#   [experimental] !DD_ENV & WEAVE_TRACE_STREAM: log trace tree traces to a W&B StreamTable
#     only captures trace calls, not other library instrumentation as added by datadog
#   None: DummyTrace that does nothing


import contextvars
import dataclasses
import json
import logging
import multiprocessing
import os
import time
import typing

from weave.legacy.weave import environment, logs, stream_data_interfaces


# Thanks co-pilot!
class DummySpan:
    def __init__(self, *args, **kwargs):  # type: ignore
        self.args = args
        self.log_indent_token = None

    def __enter__(self):  # type: ignore
        logging.debug("-> %s", self.args[0])
        self.log_indent_token = logs.increment_indent()
        return self

    def __exit__(self, *args, **kwargs):  # type: ignore
        logs.reset_indent(self.log_indent_token)
        logging.debug("<- %s", self.args[0])

    def set_tag(self, key, unredacted_val, redacted_val=None):  # type: ignore
        pass

    def set_meta(self, *args, **kwargs):  # type: ignore
        pass

    def set_metric(self, *args, **kwargs):  # type: ignore
        pass

    def finish(self, *args, **kwargs):  # type: ignore
        pass


class TraceContext:
    def __getstate__(self) -> dict:  # type: ignore
        return {}

    def __setstate__(self, state: dict) -> None:  # type: ignore
        pass


class ContextProvider:
    def activate(self, context: TraceContext) -> None:  # type: ignore
        pass


class DummyTrace:
    def trace(self, *args, **kwargs):  # type: ignore
        return DummySpan(*args)

    @property
    def context_provider(self) -> ContextProvider:  # type: ignore
        return ContextProvider()

    def current_trace_context(self) -> typing.Optional[TraceContext]:  # type: ignore
        return None

    def current_span(self):  # type: ignore
        return None 

    def current_root_span(self):  # type: ignore
        return None


_weave_trace_span: contextvars.ContextVar[typing.Optional["WeaveTraceSpan"]] = (
    contextvars.ContextVar("_weave_trace_span", default=None)
)


_weave_trace_stream = None


def weave_trace_stream():  # type: ignore
    global _weave_trace_stream
    if _weave_trace_stream is None:
        from weave.legacy.weave.wandb_interface.wandb_stream_table import StreamTable

        _weave_trace_stream = StreamTable(os.getenv("WEAVE_TRACE_STREAM"))
    return _weave_trace_stream


def span_count(span):  # type: ignore
    if span.child_spans is None:
        return 1
    return 1 + sum([span_count(child) for child in span.child_spans])


class WeaveTraceSpan:
    def __init__(self, name):  # type: ignore
        from .ops_domain import trace_tree

        self.log_indent_token = None
        self._token = None
        self.span = trace_tree.Span(_name=name)
        self._parent = None

    def total_span_count(self):  # type: ignore
        return span_count(self.span)

    def __enter__(self):  # type: ignore
        parent = _weave_trace_span.get()
        if parent is not None:
            if parent.span.child_spans is None:
                parent.span.child_spans = []
            parent.span.child_spans.append(self.span)
            self._parent = parent

        self._token = _weave_trace_span.set(self)
        self.span.start_time_ms = int(time.time() * 1000)
        return self

    def __exit__(self, *args, **kwargs):  # type: ignore
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
    def attributes(self):  # type: ignore
        if self.span.attributes is None:
            self.span.attributes = {}
        return self.span.attributes

    def set_tag(self, key, unredacted_val, redacted_val=None):  # type: ignore
        if "tags" not in self.attributes:
            self.attributes["tags"] = {}
        if not environment.disable_weave_pii():
            self.attributes["tags"][key] = unredacted_val
        elif redacted_val is not None:
            self.attributes["tags"][key] = redacted_val

    def set_meta(self, key, unredacted_val, redacted_val=None):  # type: ignore
        if "metadata" not in self.attributes:
            self.attributes["metadata"] = {}
        if not environment.disable_weave_pii():
            self.attributes["metadata"][key] = unredacted_val
        elif redacted_val is not None:
            self.attributes["metadata"][key] = redacted_val

    def set_metric(self, key, unredacted_val, redacted_val=None):  # type: ignore
        if "metrics" not in self.attributes:
            self.attributes["metrics"] = {}
        if not environment.disable_weave_pii():
            self.attributes["metrics"][key] = unredacted_val
        elif redacted_val is not None:
            self.attributes["metrics"][key] = redacted_val

    def finish(self, *args, **kwargs):  # type: ignore
        pass


class WeaveTrace:
    def __init__(self):  # type: ignore
        self._stream_table = None

    def trace(self, name, *args, **kwargs):  # type: ignore
        return WeaveTraceSpan(name, *args)

    @property
    def context_provider(self) -> ContextProvider:
        return ContextProvider()

    def current_trace_context(self) -> typing.Optional[TraceContext]:
        return None

    def current_span(self):  # type: ignore
        return _weave_trace_span.get()

    def current_root_span(self):  # type: ignore
        cur_span = _weave_trace_span.get()
        while cur_span is not None and cur_span._parent is not None:
            cur_span = cur_span._parent
        return cur_span


def dd_span_to_weave_span(dd_span) -> stream_data_interfaces.TraceSpanDict:  # type: ignore
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


def send_proc(queue):  # type: ignore
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
    def __init__(self, orig_writer):  # type: ignore
        self._orig_writer = orig_writer
        self._queue = multiprocessing.Queue()
        self._proc = multiprocessing.Process(
            target=send_proc, args=(self._queue,), daemon=True
        )

    def recreate(self):  # type: ignore
        return WeaveWriter(self._orig_writer.recreate())

    def stop(self, timeout=None):  # type: ignore
        self._orig_writer.stop(timeout)

    def _ensure_started(self):  # type: ignore
        if not self._proc.is_alive():
            self._proc.start()

    def write(self, spans):  # type: ignore
        if len(spans) == 1:
            return
        self._ensure_started()
        self._queue.put([dd_span_to_weave_span(s) for s in spans])
        self._orig_writer.write(spans)

    def flush_queue(self):  # type: ignore
        self._orig_writer.flush_queue()


def patch_ddtrace_set_tag():  # type: ignore
    from inspect import signature

    from ddtrace import span as ddtrace_span

    set_tag_signature = signature(ddtrace_span.Span.set_tag)

    # replaces ddtrace.Span.set_tag and ddtrace.Span.set_metric if not patched already
    if "redacted_val" not in set_tag_signature.parameters:
        old_set_tag = ddtrace_span.Span.set_tag
        old_set_metric = ddtrace_span.Span.set_metric

        # Only logged redacted values if flag is on
        def set_tag(self, key, unredacted_val=None, redacted_val=None):  # type: ignore
            if redacted_val is not None and environment.disable_weave_pii():
                old_set_tag(self, key, redacted_val)
            elif (
                unredacted_val is not None
                and not environment.disable_weave_pii()
                or "_dd." in key
            ):
                old_set_tag(self, key, unredacted_val)

        # Log metric if flag is off or if flag is on and redacted
        def set_metric(self, key, val, is_pii_redacted=False):  # type: ignore
            if not environment.disable_weave_pii() or is_pii_redacted or "_dd." in key:
                old_set_metric(self, key, val)

        ddtrace_span.Span.set_metric = set_metric
        ddtrace_span.Span.set_tag = set_tag


def tracer():  # type: ignore
    if os.getenv("DD_ENV"):
        from ddtrace import tracer as ddtrace_tracer

        patch_ddtrace_set_tag()
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
    def __init__(self, *args, **kwargs):  # type: ignore
        pass

    def increment(self, *args, **kwargs):  # type: ignore
        pass

    def decrement(self, *args, **kwargs):  # type: ignore
        pass

    def gauge(self, *args, **kwargs):  # type: ignore
        pass

    def flush(self, *args, **kwargs):  # type: ignore
        pass


_STATSD = None


def _initialize_statsd():  # type: ignore
    if os.getenv("DD_ENV"):
        from datadog import initialize, statsd

        initialize(statsd_disable_buffering=False)
        return statsd
    else:
        return DummyStatsd()


def statsd():  # type: ignore
    global _STATSD
    if _STATSD is None:
        _STATSD = _initialize_statsd()

    return _STATSD


def datadog_is_enabled():  # type: ignore
    return os.getenv("DD_ENV")
