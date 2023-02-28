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
import warnings

from . import environment


class LogFormat(enum.Enum):
    PRETTY = "pretty"
    DATADOG = "datadog"


@dataclasses.dataclass
class LogSettings:
    format: LogFormat
    level: str


default_log_format = "[%(asctime)s] %(levelname)s in %(module)s (Thread Name: %(threadName)s): %(message)s"


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


def env_log_level() -> typing.Any:
    # Default to only showing ERROR logs, unless otherwise specified
    level = os.environ.get("WEAVE_LOG_LEVEL", "ERROR")
    if os.environ.get("WEAVE_SERVER_ENABLE_LOGGING"):
        level = "INFO"
    return logging.getLevelName(level)


def silence_mpl() -> None:
    mpl_logger = logging.getLogger("matplotlib")
    if mpl_logger:
        mpl_logger.setLevel(logging.CRITICAL)


def setup_handler(hander: logging.Handler, settings: LogSettings) -> None:
    level = logging.getLevelName(settings.level)
    formatter = logging.Formatter(default_log_format)
    if settings.format == LogFormat.DATADOG:
        formatter = jsonlogger.JsonFormatter(
            "%(levelname)s [%(name)s] [%(filename)s:%(lineno)d] "
            "[dd.trace_id=%(dd.trace_id)s dd.span_id=%(dd.span_id)s] %(message)s",
            timestamp=True,
        )
    hander.setFormatter(formatter)
    hander.setLevel(level)


def enable_stream_logging(
    logger: typing.Optional[logging.Logger] = None,
    wsgi_stream_settings: typing.Optional[LogSettings] = None,
    pid_logfile_settings: typing.Optional[LogSettings] = None,
    server_logfile_settings: typing.Optional[LogSettings] = None,
) -> None:
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
        log_filename = get_logfile_path(f"server.log")
        if log_filename:
            handler = logging.FileHandler(log_filename, mode="w")
            setup_handler(handler, server_logfile_settings)
            logger.addHandler(handler)


def configure_logger() -> None:
    # Disable ddtrace logs, not sure why they're turned on.
    ddtrace_logs = logging.getLogger("ddtrace")
    ddtrace_logs.setLevel(logging.ERROR)

    logger = logging.getLogger("root")
    logger.setLevel(env_log_level())

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
                wsgi_stream_settings=LogSettings(LogFormat.PRETTY, "INFO"),
                pid_logfile_settings=LogSettings(LogFormat.PRETTY, "INFO"),
            )
        else:
            # This is the default case. Log to a file for this process, but
            # do not write to standard out/error. This is important because
            # when you run Weave in a notebook, it'll create a server, but
            # we don't want the logs to show up in the notebook.
            enable_stream_logging(
                logger,
                pid_logfile_settings=LogSettings(LogFormat.PRETTY, "INFO"),
            )
    else:
        if dd_env == "ci":
            # CI expects logs in the pid logfile
            enable_stream_logging(
                logger,
                wsgi_stream_settings=LogSettings(LogFormat.PRETTY, "INFO"),
                pid_logfile_settings=LogSettings(LogFormat.PRETTY, "INFO"),
            )
        elif environment.wandb_production():
            # Only log in the datadog format to the wsgi stream
            enable_stream_logging(
                logger,
                wsgi_stream_settings=LogSettings(LogFormat.DATADOG, "DEBUG"),
            )
        else:
            # Otherwise this is dev mode with datadog logging turned on.
            # Log to standard out and a known filename that the datadog
            # agent can watch.
            enable_stream_logging(
                logger,
                wsgi_stream_settings=LogSettings(LogFormat.PRETTY, "INFO"),
                server_logfile_settings=LogSettings(LogFormat.DATADOG, "DEBUG"),
            )
