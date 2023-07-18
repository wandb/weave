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
from .. import graph

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ExecutionResult:
    """A dataclass representing the result of a function call.  This is used to pass the result of a function call
    to the monitor callback.
    """

    start_datetime: datetime.datetime
    end_datetime: datetime.datetime
    args: tuple[typing.Any, ...]
    kwargs: dict[str, typing.Any]
    output: typing.Any
    exception: typing.Optional[Exception]
    id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))

    def get(self) -> typing.Any:
        if self.exception is not None:
            raise self.exception
        return self.output


@dataclasses.dataclass
class MonitorRecord:
    _execution_result: ExecutionResult
    _input_preprocessor: typing.Callable[..., typing.Any]
    _output_postprocessor: typing.Callable[..., typing.Any] = lambda x: x
    _additional_data: dict = dataclasses.field(default_factory=dict)
    _on_log: typing.Optional[typing.Callable[..., None]] = None

    @property
    def id(self) -> str:
        return self._execution_result.id

    def get(self) -> typing.Any:
        return self._execution_result.get()

    def add_data(self, data: dict) -> None:
        self._additional_data.update(data)

    def finalize(self) -> None:
        if self._on_log is not None:
            self._on_log(self)
            self._on_log = None
        else:
            logger.warning("MonitorRecord already finalized")

    @property
    def inputs(self) -> dict:
        return self._input_preprocessor(
            *self._execution_result.args, **self._execution_result.kwargs
        )

    @property
    def output(self) -> typing.Any:
        return self._output_postprocessor(self._execution_result.output)

    def as_dict(self) -> dict:
        exception = self._execution_result.exception
        return {
            "result_id": self._execution_result.id,
            "start_datetime": self._execution_result.start_datetime,
            "end_datetime": self._execution_result.end_datetime,
            "latency_ms": (
                self._execution_result.end_datetime.timestamp()
                - self._execution_result.start_datetime.timestamp()
            )
            * 1000,
            "inputs": self.inputs,
            "output": self.output,
            "exception": (
                f"{type(exception).__name__}: {str(exception)}"
                if exception is not None
                else None
            ),
            **self._additional_data,
        }

    def __repr__(self) -> str:
        return f"MonitorRecord({self._execution_result.id})"


def monitor(
    stream_name: typing.Optional[str] = None,
    *,
    project_name: str,
    entity_name: str,
    input_preprocessor: typing.Optional[
        typing.Callable[..., dict[str, typing.Any]]
    ] = None,
    output_postprocessor: typing.Optional[
        typing.Callable[..., dict[str, typing.Any]]
    ] = None,
    auto_log: bool = True,
    raise_on_error: bool = True,
) -> typing.Callable[..., typing.Callable[..., MonitorRecord]]:
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

    def decorator(
        fn: typing.Callable[..., typing.Any]
    ) -> typing.Callable[..., MonitorRecord]:
        return MonitoredFunction(
            fn=fn,
            stream_name=stream_name or _get_default_fn_name(fn),
            project_name=project_name,
            entity_name=entity_name,
            input_preprocessor=input_preprocessor,
            output_postprocessor=output_postprocessor,
            auto_log=auto_log,
            raise_on_error=raise_on_error,
        )

    return decorator


class MonitoredFunction:
    _fn: typing.Callable[..., typing.Any]
    _tracked_fn: typing.Callable[..., ExecutionResult]
    _stream_table: StreamTable
    _input_preprocessor: typing.Callable[..., dict[str, typing.Any]]
    _output_preprocessor: typing.Callable[..., dict[str, typing.Any]]
    _auto_log: bool
    _disabled: bool
    _raise_on_error: bool

    def __init__(
        self,
        *,
        fn: typing.Callable[..., typing.Any],
        stream_name: str,
        project_name: str,
        entity_name: str,
        input_preprocessor: typing.Optional[
            typing.Callable[..., dict[str, typing.Any]]
        ] = None,
        output_postprocessor: typing.Optional[
            typing.Callable[..., dict[str, typing.Any]]
        ] = None,
        auto_log: bool = True,
        raise_on_error: bool = True,
    ):
        self._fn = fn
        self._tracked_fn = _track(raise_on_error)(fn)
        self._disabled = False
        self._auto_log = auto_log
        self._raise_on_error = raise_on_error

        try:
            self._stream_table = StreamTable(
                table_name=stream_name,
                project_name=project_name,
                entity_name=entity_name,
            )
        except errors.WeaveWandbAuthenticationException:
            self._disabled = True
            logger.error("Monitoring disabled because WANDB_API_KEY is not set.")
            print("Couldn't find W&B API key, disabling monitoring.", file=sys.stderr)
            print(
                "Set the WANDB_API_KEY env variable to enable monitoring.",
                file=sys.stderr,
            )

        self._input_preprocessor = input_preprocessor or self._default_input_processor
        self._output_postprocessor = output_postprocessor or (lambda x: x)

    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        execution_record = self._tracked_fn(*args, **kwargs)
        monitor_record = MonitorRecord(
            execution_record,
            self._input_preprocessor,
            self._output_postprocessor,
        )
        if not self._disabled and self._auto_log:
            self._direct_log(monitor_record)
        else:
            monitor_record._on_log = self._direct_log
        return monitor_record

    # to support instance methods
    def __get__(self, instance: typing.Any, owner: typing.Any) -> "MonitoredFunction":
        if instance is None:
            return self
        else:
            self._fn = self._fn.__get__(instance, owner)
            self._tracked_fn = _track(self._raise_on_error)(self._fn)
            return self

    def _direct_log(self, record: MonitorRecord) -> None:
        self._stream_table.log(record.as_dict())

    def _default_input_processor(self, *args: typing.Any, **kwargs: typing.Any) -> dict:
        arg_dict = _arguments_to_dict(self._fn, args, kwargs)
        if "self" in arg_dict:
            del arg_dict["self"]
        return arg_dict

    def rows(self) -> graph.Node:
        return self._stream_table.rows()


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


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _get_default_fn_name(fn: typing.Callable) -> str:
    fn_file_name = _sanitize_name(os.path.basename(inspect.getfile(fn)))
    if fn_file_name.endswith(".py"):
        fn_file_name = fn_file_name[:-3]
    fn_name = _sanitize_name(fn.__name__)

    return f"{fn_file_name}-{fn_name}"


def _track(
    raise_on_error: bool = True,
) -> typing.Callable[..., typing.Callable[..., ExecutionResult]]:
    """A low-level utility for tracking function executions."""

    def function_monitor_decorator(
        fn: typing.Callable[..., typing.Any]
    ) -> typing.Callable[..., ExecutionResult]:
        def wrapped_fn(*args: typing.Any, **kwargs: typing.Any) -> "ExecutionResult":
            output = None
            exception = None
            args = args
            kwargs = kwargs
            try:
                start_datetime = datetime.datetime.now()
                output = fn(*args, **kwargs)
                end_datetime = datetime.datetime.now()
            except Exception as e:
                end_datetime = datetime.datetime.now()
                if raise_on_error:
                    raise e
                exception = e
            return ExecutionResult(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                args=args,
                kwargs=kwargs,
                output=output,
                exception=exception,
            )

        return wrapped_fn

    return function_monitor_decorator
