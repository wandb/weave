import dataclasses
import datetime
import inspect
import os
import re
import sys
import typing
import uuid
import logging


from ..wandb_interface.wandb_stream_table import StreamTableAsync
from ..wandb_interface.wandb_lite_run import WeaveWandbRunException

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
            "output": self._execution_result.output,
            "exception": str(self._execution_result.exception)
            if self._execution_result.exception is not None
            else "",
            **self._additional_data,
        }

    def __repr__(self) -> str:
        return f"MonitorRecord({self._execution_result.id})"


def monitor(
    stream_name: typing.Optional[str] = None,
    project_name: typing.Optional[str] = None,
    entity_name: typing.Optional[str] = None,
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
        input_preprocessor (typing.Callable[..., typing.Any]):  A function that takes the kwargs of the decorated function and
            returns a dictionary of key value pairs to log.
        output_postprocessor (typing.Callable[..., typing.Any]):  A function that takes the return value of the decorated function
            and returns a dictionary or single value to log.
    """

    def decorator(
        fn: typing.Callable[..., typing.Any]
    ) -> typing.Callable[..., MonitorRecord]:
        mon = MonitorStream(
            fn,
            stream_name,
            project_name,
            entity_name,
            input_preprocessor,
            output_postprocessor,
            auto_log,
        )
        tracked_fn = track(raise_on_error)(fn)

        def wrapped_fn(*args: typing.Any, **kwargs: typing.Any) -> MonitorRecord:
            logger.debug("decorating %s", fn)
            execution_record = tracked_fn(*args, **kwargs)
            monitor_record = mon.record(execution_record)
            return monitor_record

        return wrapped_fn

    return decorator


def track(
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


class MonitorStream:
    _fn: typing.Callable[..., typing.Any]
    _stream_table: StreamTableAsync
    _input_preprocessor: typing.Callable[..., dict[str, typing.Any]]
    _output_preprocessor: typing.Callable[..., dict[str, typing.Any]]
    _auto_log: bool

    def __init__(
        self,
        fn: typing.Callable[..., typing.Any],
        stream_name: typing.Optional[str] = None,
        project_name: typing.Optional[str] = None,
        entity_name: typing.Optional[str] = None,
        input_preprocessor: typing.Optional[
            typing.Callable[..., dict[str, typing.Any]]
        ] = None,
        output_postprocessor: typing.Optional[
            typing.Callable[..., dict[str, typing.Any]]
        ] = None,
        auto_log: bool = True,
    ):
        self._fn = fn
        self._disabled = False
        self._auto_log = auto_log

        try:
            self._stream_table = StreamTableAsync(
                stream_name or _get_default_fn_name(fn),
                project_name or "monitoring",
                entity_name,
            )
        except WeaveWandbRunException:
            self._disabled = True
            logger.error("Monitoring disabled because WANDB_API_KEY is not set.")
            print("Couldn't find W&B API key, disabling monitoring.", file=sys.stderr)
            print(
                "Set the WANDB_API_KEY env variable to enable monitoring.",
                file=sys.stderr,
            )

        self._input_preprocessor = input_preprocessor or self._default_input_processor
        self._output_postprocessor = output_postprocessor or (lambda x: x)

    def _direct_log(self, record: MonitorRecord) -> None:
        self._stream_table.log(lambda: record.as_dict())

    def record(self, result: ExecutionResult) -> MonitorRecord:
        monitor_record = MonitorRecord(
            result,
            self._input_preprocessor,
            self._output_postprocessor,
        )
        if not self._disabled and self._auto_log:
            self._direct_log(monitor_record)
        else:
            monitor_record._on_log = self._direct_log
        return monitor_record

    def _default_input_processor(self, *args: typing.Any, **kwargs: typing.Any) -> dict:
        arg_dict = _arguments_to_dict(self._fn, args, kwargs)
        if "self" in arg_dict:
            del arg_dict["self"]
        return arg_dict


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
    fn_name = _sanitize_name(fn.__name__)

    return f"{fn_file_name}-{fn_name}"
