import os
import typing

# Thanks co-pilot!
class DummySpan:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        pass

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
        return DummySpan()

    @property
    def context_provider(self) -> ContextProvider:
        return ContextProvider()

    def current_trace_context(self) -> typing.Optional[TraceContext]:
        return None

    def current_span(self):
        return None

    def current_root_span(self):
        return None


def tracer():
    if os.getenv("DD_ENV"):
        from ddtrace import tracer as ddtrace_tracer

        return ddtrace_tracer
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

        initialize()
        return statsd
    else:
        return DummyStatsd()


def statsd():
    global _STATSD
    if _STATSD is None:
        _STATSD = _initialize_statsd()

    return _STATSD


from ddtrace import tracer as ddtrace_tracer

x = ddtrace_tracer.current_trace_context()


def datadog_is_enabled():
    return os.getenv("DD_ENV")
