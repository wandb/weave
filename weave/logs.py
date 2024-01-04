import json
import dataclasses
import enum
import pathlib
import warnings
import os
import pathlib
import logging
import logging.config
from logging.handlers import WatchedFileHandler
from flask.logging import wsgi_errors_stream
from pythonjsonlogger import jsonlogger
import typing
import contextlib
import contextvars
import warnings

from . import environment


class LogFormat(enum.Enum):
    PRETTY = "pretty"
    DATADOG = "datadog"
    JSON = "json"


@dataclasses.dataclass
class LogSettings:
    format: LogFormat
    level: typing.Optional[int]


_log_indent: contextvars.ContextVar[int] = contextvars.ContextVar(
    "_log_indent", default=0
)


def increment_indent() -> contextvars.Token[int]:
    indent = _log_indent.get()
    return _log_indent.set(indent + 1)


def reset_indent(token: contextvars.Token[int]) -> None:
    _log_indent.reset(token)


@contextlib.contextmanager
def indent_logs() -> typing.Iterator:
    token = increment_indent()
    try:
        yield
    finally:
        reset_indent(token)


def get_indent() -> int:
    return _log_indent.get()


class IndentFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        indent = get_indent()
        record.indent = "  " * indent  # type: ignore
        return True


default_log_format = "[%(asctime)s] %(levelname)s in %(module)s (Thread Name: %(threadName)s): %(indent)s%(message)s"


def get_logdir() -> typing.Optional[str]:
    logdir = "/tmp/weave/log"
    try:
        pathlib.Path(logdir).mkdir(exist_ok=True, parents=True)
    except OSError:
        warnings.warn(
            f"weave: Unable make log dir '{logdir}'. Filesystem logging will be disabled for "
            f"the remainder of this session. To enable filesystem logging, ensure the path is writable "
            f"and restart the server."
        )
        return None
    return logdir


def get_logfile_path(logfile_path: str) -> typing.Optional[str]:
    logdir = get_logdir()
    if logdir is None:
        return None
    full_path = pathlib.Path(logdir) / logfile_path
    try:
        full_path.touch()
    except OSError:
        warnings.warn(
            f"weave: Unable to touch logfile at '{full_path}'. Filesystem logging will be disabled for "
            f"the remainder of this session. To enable filesystem logging, ensure the path is writable "
            f"and restart the server."
        )
        return None
    return str(full_path)


def default_log_filename() -> typing.Optional[str]:
    pid = os.getpid()
    return get_logfile_path(f"{pid}.log")


def env_log_level() -> int:
    level_str_from_env = os.environ.get("WEAVE_LOG_LEVEL")
    if level_str_from_env:
        level_int_from_env = logging.getLevelName(level_str_from_env.upper())
        if isinstance(level_int_from_env, int):
            return level_int_from_env
        print(
            f'WEAVE_LOG_LEVEL environment variable value "{level_str_from_env}" is invalid.'
        )

    if os.environ.get("WEAVE_SERVER_ENABLE_LOGGING"):
        return logging.INFO

    # Default to only showing ERROR logs
    return logging.ERROR


def silence_mpl() -> None:
    mpl_logger = logging.getLogger("matplotlib")
    if mpl_logger:
        mpl_logger.setLevel(logging.CRITICAL)


def set_global_log_level(level: int) -> None:
    # Unused, but runs through all existing loggers and sets their level to the given level
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for logger_name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)


def print_handlers(logger: logging.Logger) -> None:
    # For debugging
    print(f"Handlers for logger '{logger.name}':")
    for handler in logger.handlers:
        print(f"  {handler}")


def print_all_handlers() -> None:
    # For debugging
    root_logger = logging.getLogger()
    print_handlers(root_logger)

    for logger_name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        print_handlers(logger)


class WeaveJSONEncoder(jsonlogger.JsonEncoder):
    def default(self, obj: typing.Any) -> typing.Any:
        if obj is None:
            # This is needed because datadog strips keys with null values from logs
            return "<<_WEAVE_NONE_>>"
        return super().default(obj)  # type: ignore[no-untyped-call]


def setup_handler(handler: logging.Handler, settings: LogSettings) -> None:
    formatter = logging.Formatter(default_log_format)
    if settings.format == LogFormat.DATADOG:
        formatter = jsonlogger.JsonFormatter(
            "%(levelname)s [%(name)s] [%(filename)s:%(lineno)d] "
            "[dd.trace_id=%(dd.trace_id)s dd.span_id=%(dd.span_id)s] %(message)s",
            timestamp=True,
            json_encoder=WeaveJSONEncoder,
        )  # type: ignore[no-untyped-call]
    elif settings.format == LogFormat.JSON:
        formatter = jsonlogger.JsonFormatter(
            "%(levelname)s [%(name)s] [%(filename)s:%(lineno)d] %(message)s",
            timestamp=True,
            json_encoder=WeaveJSONEncoder,
        )  # type: ignore[no-untyped-call]
    handler.addFilter(IndentFilter())
    handler.setFormatter(formatter)
    if settings.level is not None:
        handler.setLevel(settings.level)


_LOGGING_CONFIGURED = False


def enable_stream_logging(
    logger: typing.Optional[logging.Logger] = None,
    wsgi_stream_settings: typing.Optional[LogSettings] = None,
    pid_logfile_settings: typing.Optional[LogSettings] = None,
    server_logfile_settings: typing.Optional[LogSettings] = None,
) -> None:
    global _LOGGING_CONFIGURED
    _LOGGING_CONFIGURED = True

    handler: logging.Handler
    logger = logger or logging.getLogger("root")

    if wsgi_stream_settings is not None:
        handler = logging.StreamHandler(wsgi_errors_stream)  # type: ignore
        setup_handler(handler, wsgi_stream_settings)
        logger.addHandler(handler)

    if pid_logfile_settings is not None:
        log_filename = default_log_filename()
        if log_filename:
            handler = WatchedFileHandler(log_filename, mode="w")
            setup_handler(handler, pid_logfile_settings)
            logger.addHandler(handler)

    if server_logfile_settings is not None:
        log_filename = get_logfile_path("server.log")
        if log_filename:
            handler = logging.FileHandler(log_filename, mode="w")
            setup_handler(handler, server_logfile_settings)
            logger.addHandler(handler)


def configure_logger() -> None:
    if _LOGGING_CONFIGURED:
        return
    # Disable ddtrace logs, not sure why they're turned on.
    ddtrace_logs = logging.getLogger("ddtrace")
    ddtrace_logs.setLevel(logging.ERROR)

    logger = logging.getLogger("root")
    logger.setLevel(env_log_level())

    # Remove StreamHandler from the root logger to avoid stdout logging
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            logger.removeHandler(handler)

    dd_env = os.getenv("DD_ENV")
    enable_datadog = dd_env
    if not enable_datadog:
        # This is the standard path for users.
        if os.getenv("WEAVE_SERVER_ENABLE_LOGGING"):
            # WEAVE_SERVER_ENABLE_LOGGING forces the logs to go to the wsgi
            # stream which will go to the console. We set this flag in our
            # server start scripts, so that if you run the server in its own
            # terminal, you get the logs.
            enable_stream_logging(
                logger,
                wsgi_stream_settings=LogSettings(
                    environment.weave_log_format(LogFormat.PRETTY), level=None
                ),
                pid_logfile_settings=LogSettings(
                    environment.weave_log_format(LogFormat.PRETTY), logging.INFO
                ),
            )
        else:
            # This is the default case. Log to a file for this process, but
            # do not write to standard out/error. This is important because
            # when you run Weave in a notebook, it'll create a server, but
            # we don't want the logs to show up in the notebook.
            enable_stream_logging(
                logger,
                pid_logfile_settings=LogSettings(
                    environment.weave_log_format(LogFormat.PRETTY), logging.INFO
                ),
            )
    else:
        if dd_env == "ci":
            # CI expects logs in the pid logfile
            enable_stream_logging(
                logger,
                wsgi_stream_settings=LogSettings(
                    environment.weave_log_format(LogFormat.PRETTY), logging.INFO
                ),
                pid_logfile_settings=LogSettings(
                    environment.weave_log_format(LogFormat.PRETTY), logging.INFO
                ),
            )
        elif environment.wandb_production():
            # Only log in the datadog format to the wsgi stream
            enable_stream_logging(
                logger,
                wsgi_stream_settings=LogSettings(
                    environment.weave_log_format(LogFormat.DATADOG), level=None
                ),
            )
        else:
            # Otherwise this is dev mode with datadog logging turned on.
            # Log to standard out and a known filename that the datadog
            # agent can watch.
            enable_stream_logging(
                logger,
                wsgi_stream_settings=LogSettings(
                    environment.weave_log_format(LogFormat.PRETTY), level=None
                ),
                server_logfile_settings=LogSettings(
                    environment.weave_log_format(LogFormat.DATADOG), level=None
                ),
            )
