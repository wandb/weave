import os
import pathlib
import logging
import logging.config
import typing
import warnings

pid = os.getpid()
default_log_filename = pathlib.Path(f"/tmp/weave/log/{pid}.log")
default_log_format = "[%(asctime)s] %(levelname)s in %(module)s (Thread Name: %(threadName)s): %(message)s"

fs_logging_enabled = True
try:
    default_log_filename.parent.mkdir(exist_ok=True, parents=True)
    default_log_filename.touch(exist_ok=True)
except OSError:
    warnings.warn(
        f"weave: Unable to touch logfile at '{default_log_filename}'. Filesystem logging will be disabled for "
        f"the remainder of this session. To enable filesystem logging, ensure the path is writable "
        f"and restart the server."
    )
    fs_logging_enabled = False


def env_log_level() -> typing.Any:
    # Default to only showing ERROR logs, unless otherwise specified
    level = os.environ.get("WEAVE_LOG_LEVEL", "ERROR")
    if os.environ.get("WEAVE_SERVER_ENABLE_LOGGING"):
        # WEAVE_SERVER_ENABLE_LOGGING forces DEBUG
        level = "DEBUG"
    return logging.getLevelName(level)


logging_config = {
    "version": 1,
    "formatters": {
        "default": {
            "format": default_log_format,
        }
    },
    "handlers": {
        "wsgi_file": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": default_log_filename,
            "formatter": "default",
        },
    },
    "root": {
        "level": env_log_level(),
        "handlers": ["wsgi_file"] if fs_logging_enabled else [],
    },
}

logging.config.dictConfig(logging_config)
