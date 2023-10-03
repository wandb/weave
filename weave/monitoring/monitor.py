"""Monitoring & tracing"""

import asyncio
import contextlib
import contextvars
import dataclasses
import datetime
import inspect
import sys
import typing
import uuid
import logging


from ..wandb_interface.wandb_stream_table import StreamTable
from .. import errors
from .. import graph
from .. import stream_data_interfaces

logger = logging.getLogger(__name__)

_global_monitor: typing.Optional["Monitor"] = None

_current_span: contextvars.ContextVar[typing.Optional["Span"]] = contextvars.ContextVar(
    "_current_span", default=None
)

_attributes: contextvars.ContextVar[
    typing.Dict[str, typing.Any]
] = contextvars.ContextVar("_attributes", default={})


# Matches OpenTelemetry
class StatusCode:
    UNSET = "UNSET"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


def _arguments_to_dict(
    fn: typing.Callable, args: tuple[typing.Any, ...], kwargs: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    """Given a function and arguments used to call that function, return a dictionary of key value pairs
    that are the bound arguments to the function.
    """
    sig = inspect.signature(fn)
    bound_params = sig.bind(*args, **kwargs)
    bound_params.apply_defaults()
    got_args = dict(bound_params.arguments)
    return got_args


def get_function_name(fn: typing.Callable) -> str:
    module_name = fn.__module__

    # Check if the function is bound to a class
    if inspect.ismethod(fn):
        class_name = fn.__self__.__class__.__name__
        return f"{module_name}.{class_name}.{fn.__name__}"
    else:
        return f"{module_name}.{fn.__name__}"


class Span:
    # When this is None, monitor is disabled
    _streamtable: typing.Optional[StreamTable]

    # These are OpenTelemetry standard

    parent_id: typing.Optional[str]
    trace_id: str
    id: str  # span_id
    name: str
    status_code: str = StatusCode.UNSET
    start_time: datetime.datetime
    end_time: typing.Optional[datetime.datetime]

    # OpenTelemetry does not support these.

    # Arbitrary key/value pairs. Values can be any Weave type, as
    # opposed to opentelemetry where values can only be scalars or
    # lists of homoegenous scalar types.
    attributes: dict[str, typing.Any]
    # The parameters to the function being traced.
    inputs: typing.Optional[typing.Dict[str, typing.Any]]
    # The output of the function being traced.
    output: typing.Optional[typing.Any]
    # If an exception occurred, this will be set.
    exception: typing.Optional[Exception]
    # Typically summary should contain metrics about resources used
    # during the function's execution (cpu, disk, tokens, api cost etc)
    # or other information created in the course of actually executing
    # the function.
    summary: dict[str, typing.Any]

    _autoclose: bool = True

    def __init__(
        self,
        name: str,
        _streamtable: typing.Optional[StreamTable] = None,
        parent_id: typing.Optional[str] = None,
        trace_id: typing.Optional[str] = None,
        attributes: typing.Optional[dict[str, typing.Any]] = None,
        inputs: typing.Optional[typing.Dict[str, typing.Any]] = None,
        output: typing.Optional[typing.Any] = None,
        summary: typing.Optional[dict[str, typing.Any]] = None,
    ):
        self.name = name
        self._streamtable = _streamtable
        self.parent_id = parent_id
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        self.trace_id = trace_id
        if attributes is None:
            attributes = {}
        self.attributes = attributes
        self.status_code = StatusCode.UNSET
        self.span_id = str(uuid.uuid4())
        self.start_time = datetime.datetime.now()
        self.end_time = None
        self.inputs = inputs
        self.output = output
        self.exception = None
        if summary is None:
            summary = {}
        self.summary = summary

    def close(self) -> None:
        if self.status_code == StatusCode.UNSET:
            self.status_code = StatusCode.SUCCESS
        self.end_time = datetime.datetime.now()
        if self._streamtable is not None:
            self._streamtable.log(self.asdict())

    def disable_autoclose(self) -> None:
        self._autoclose = False

    def autoclose(self) -> None:
        if self._autoclose:
            self.close()

    def asdict(self) -> stream_data_interfaces.TraceSpanDict:
        if self.end_time is None:
            raise ValueError(
                "Cannot log a span that has not been ended.  Call span.end() before logging."
            )
        start_time_s = self.start_time.timestamp()
        end_time_s = self.end_time.timestamp()
        self.summary["latency_s"] = end_time_s - start_time_s
        return {
            "parent_id": self.parent_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "status_code": self.status_code,
            "start_time_s": start_time_s,
            "end_time_s": end_time_s,
            "inputs": self.inputs,
            "output": self.output,
            "exception": (
                f"{type(self.exception).__name__}: {str(self.exception)}"
                if self.exception is not None
                else None
            ),
            "attributes": self.attributes,
            "summary": self.summary,
        }


# A type used to indicate that inputs is guaranteed to be set, for pre and post process callbacks.
class SpanWithInputs(Span):
    inputs: typing.Dict[str, typing.Any]


class SpanWithInputsAndOutput(Span):
    inputs: typing.Dict[str, typing.Any]
    output: typing.Any


@dataclasses.dataclass
class Monitor:
    # When this is None, monitor is disabled
    _streamtable: typing.Optional[StreamTable]

    _showed_not_logging_warning: bool = False

    @contextlib.contextmanager
    def span(self, name: str) -> typing.Iterator[Span]:
        if not self._showed_not_logging_warning and self._streamtable is None:
            self._showed_not_logging_warning = True
            print(
                "WARNING: Not logging spans.  Call weave.monitor.init_monitor() to enable logging."
            )

        parent_span = _current_span.get()
        trace_id = None
        if parent_span is not None:
            parent_id = parent_span.span_id
            trace_id = parent_span.trace_id
        else:
            parent_id = None
        span = Span(name, self._streamtable, parent_id, trace_id, _attributes.get())
        token = _current_span.set(span)
        try:
            yield span
        finally:
            span.autoclose()
            _current_span.reset(token)

    @contextlib.contextmanager
    def attributes(self, attributes: typing.Dict[str, typing.Any]) -> typing.Iterator:
        cur_attributes = {**_attributes.get()}
        cur_attributes.update(attributes)

        token = _attributes.set(cur_attributes)
        try:
            yield
        finally:
            _attributes.reset(token)

    def trace(
        self,
        preprocess: typing.Optional[typing.Callable] = None,
        postprocess: typing.Optional[typing.Callable] = None,
    ) -> typing.Callable[..., typing.Callable[..., typing.Any]]:
        def decorator(fn: typing.Callable[..., typing.Any]) -> typing.Any:
            if asyncio.iscoroutinefunction(fn):

                async def async_wrapper(
                    *args: typing.Any, **kwargs: typing.Any
                ) -> typing.Any:
                    attributes = kwargs.pop("monitor_attributes", {})
                    with self.attributes(attributes):
                        with self.span(get_function_name(fn)) as span:
                            span.inputs = _arguments_to_dict(fn, args, kwargs)
                            try:
                                span.output = await fn(*args, **kwargs)
                            except Exception as e:
                                span.status_code = StatusCode.ERROR
                                span.exception = e
                                raise
                            return span.output

                return async_wrapper

            else:

                def sync_wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                    attributes = kwargs.pop("monitor_attributes", {})
                    with self.attributes(attributes):
                        with self.span(get_function_name(fn)) as span:
                            span.inputs = _arguments_to_dict(fn, args, kwargs)
                            if preprocess:
                                preprocess(span)
                            try:
                                span.output = fn(*args, **kwargs)
                                output = span.output
                                if postprocess:
                                    output = postprocess(span)
                            except Exception as e:
                                span.status_code = StatusCode.ERROR
                                span.exception = e
                                raise
                            return output

                return sync_wrapper

        return decorator

    def rows(self) -> typing.Optional[graph.Node]:
        if self._streamtable is None:
            return None
        return self._streamtable.rows()


def _init_monitor_streamtable(stream_key: str) -> typing.Optional[StreamTable]:
    tokens = stream_key.split("/")
    if len(tokens) == 2:
        project_name, stream_name = tokens
        entity_name = None
    elif len(tokens) == 3:
        entity_name, project_name, stream_name = tokens
    else:
        raise ValueError(
            "stream_key must be of the form 'entity/project/stream_name' or 'project/stream_name'"
        )

    stream_table = None
    try:
        stream_table = StreamTable(
            table_name=stream_name,
            project_name=project_name,
            entity_name=entity_name,
        )
    except errors.WeaveWandbAuthenticationException:
        logger.error("Monitoring disabled because WANDB_API_KEY is not set.")
        print("Couldn't find W&B API key, disabling monitoring.", file=sys.stderr)
        print(
            "Set the WANDB_API_KEY env variable to enable monitoring.",
            file=sys.stderr,
        )
    return stream_table


def default_monitor() -> Monitor:
    """Get the global Monitor."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = Monitor(None)
    return _global_monitor


def new_monitor(stream_key: str) -> Monitor:
    """Create a new Monitor"""
    return Monitor(_init_monitor_streamtable(stream_key))


def init_monitor(stream_key: str) -> Monitor:
    """Initialize the global monitor and return it."""
    global _global_monitor
    stream_table = _init_monitor_streamtable(stream_key)
    if _global_monitor is None:
        _global_monitor = Monitor(stream_table)
    else:
        _global_monitor._streamtable = stream_table
    return _global_monitor
