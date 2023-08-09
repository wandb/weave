import contextlib
import contextvars
import dataclasses
import datetime
import inspect
import os
import re
import sys
import typing
import uuid
import logging


from ..wandb_interface.wandb_stream_table import StreamTable
from .. import errors

logger = logging.getLogger(__name__)

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
    return dict(bound_params.arguments)


def get_function_name(fn: typing.Callable) -> str:
    module_name = fn.__module__

    # Check if the function is bound to a class
    if inspect.ismethod(fn):
        class_name = fn.__self__.__class__.__name__
        return f"{module_name}.{class_name}.{fn.__name__}"
    else:
        return f"{module_name}.{fn.__name__}"


class Span:
    parent_id: typing.Optional[str]
    trace_id: str
    span_id: str
    name: str
    status_code: typing.Optional[str] = None
    start_time: datetime.datetime
    end_time: typing.Optional[datetime.datetime]
    inputs: typing.Optional[typing.Dict[str, typing.Any]]
    output: typing.Optional[typing.Any]
    exception: typing.Optional[Exception]

    def __init__(self, parent_id: typing.Optional[str], trace_id: str, name: str):
        self.parent_id = parent_id
        self.trace_id = trace_id
        self.name = name
        self.status_code = StatusCode.UNSET
        self.span_id = str(uuid.uuid4())
        self.start_time = datetime.datetime.now()
        self.end_time = None
        self.inputs = None
        self.output = None
        self.exception = None

    def end(self):
        if self.status_code == StatusCode.UNSET:
            self.status_code = StatusCode.SUCCESS
        self.end_time = datetime.datetime.now()

    def asdict(self):
        return {
            "parent_id": self.parent_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "status_code": self.status_code,
            "start_time_ms": self.start_time.timestamp() * 1000,
            "end_time_ms": self.end_time.timestamp() * 1000,
            "inputs": self.inputs,
            "output": self.output,
            "exception": (
                f"{type(self.exception).__name__}: {str(self.exception)}"
                if self.exception is not None
                else None
            ),
            "attributes": {"hello": 5},
        }


_current_span: contextvars.ContextVar[typing.Optional[Span]] = contextvars.ContextVar(
    "_current_span", default=None
)


@dataclasses.dataclass
class Monitor:
    _streamtable: StreamTable

    @contextlib.contextmanager
    def span(self, name: str):
        parent_span = _current_span.get()
        if parent_span is not None:
            parent_id = parent_span.span_id
            trace_id = parent_span.trace_id
        else:
            parent_id = None
            trace_id = str(uuid.uuid4())
        span = Span(parent_id, trace_id, name)
        token = _current_span.set(span)
        try:
            yield span
        finally:
            span.end()
            self._streamtable.log(span.asdict())
            _current_span.reset(token)

    def trace(self) -> typing.Callable[..., typing.Callable[..., typing.Any]]:
        def decorator(fn: typing.Callable[..., typing.Any]) -> typing.Any:
            def wrapped(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                with self.span(get_function_name(fn)) as span:
                    span.inputs = _arguments_to_dict(fn, args, kwargs)
                    try:
                        span.output = fn(*args, **kwargs)
                    except Exception as e:
                        span.status_code = StatusCode.ERROR
                        span.exception = e
                        raise
                    return span.output

            return wrapped

        return decorator


@dataclasses.dataclass
class DummyMonitor(Monitor):
    pass


def monitor(
    stream_key: typing.Optional[str],
) -> Monitor:
    """Monitor a function.  This is a function decorator for performantely monitoring predictions during inference.
    Specify an input_preprocessor or output_postprocessor to have more control over what gets logged.  Each
    callbable should return a dictionary with scalar values or wandb Media objects.

    Arguments:
        stream_name (typing.Optional[str]): The name of the stream to log to. If None, the stream name will be
            inferred from the function name.
        project_name str:  The name of the W&B Project to log to.
        entity_name str:  The name of the W&B Entity to log to.
        input_preprocessor (typing.Callable[..., typing.Any]):  A function that takes the kwargs of the decorated function and
            returns a dictionary of key value pairs to log.
        output_postprocessor (typing.Callable[..., typing.Any]):  A function that takes the return value of the decorated function
            and returns a dictionary or single value to log.
        auto_log (bool):  If True, the function will automatically log the inputs and outputs of the function call. Set this
            to False if you want to add additional data to the log after the function call.
        raise_on_error (bool):  If True, the function will raise an exception if the function call raises an exception.
            If False, the function will return a MonitorRecord with the exception set.
    """
    try:
        entity_name, project_name, stream_name = stream_key.split("/", 3)
    except ValueError:
        raise ValueError("stream_key must be of the form 'entity/project/stream_name'")
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
        return DummyMonitor()

    return Monitor(stream_table)
