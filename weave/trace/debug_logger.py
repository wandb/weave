import functools
import inspect
import json
import logging
import os
import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set the logger's level to DEBUG

# # Add a StreamHandler to output logs to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)

debug_logger_context: ContextVar["DebugLogger"] = ContextVar("debug_logger")


class DebugLogger(logging.Logger):
    def __init__(self, logger: logging.Logger, func: Callable):
        super().__init__(logger.name, logger.level)
        self.logger = logger
        self.func_name = func.__name__
        self.func_file = os.path.relpath(
            inspect.getfile(func), os.path.dirname(os.path.dirname(__file__))
        )
        self.call_id = uuid.uuid4().hex[:8]

    def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1,
    ):
        if not is_xtreme_logging_enabled():
            return
        thread_id = threading.get_ident()
        timestamp = (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            + f".{int(time.time() * 1000) % 1000:03d}"
        )
        file_path = self.func_file[-30:]
        if len(file_path) > 30:
            file_path = file_path[-27:].rjust(30, ".")
        formatted_msg = (
            f"{timestamp:<23} "
            f"[Thread-{thread_id:<5}] "
            f"[Call-{self.call_id:<8}] "
            f"[{file_path:<30}:  {self.func_name:<20}] "
            f"{msg}"
        )
        self.logger._log(
            level, formatted_msg, args, exc_info, extra, stack_info, stacklevel
        )

    def debug(self, msg, *args, **kwargs):
        self._log(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._log(logging.INFO, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log(logging.WARNING, msg, args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._log(logging.CRITICAL, msg, args, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        self._log(logging.ERROR, msg, args, exc_info=exc_info, **kwargs)


def is_xtreme_logging_enabled():
    return os.environ.get("WEAVE_ENABLE_XTREME_LOGGING", "0").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def log_debug(logger: Optional[logging.Logger] = None):
    if not is_xtreme_logging_enabled():
        return lambda func: func

    if logger is None:
        logger = logging.getLogger(__name__)

    # Ensure the logger is set to DEBUG level
    logger.setLevel(logging.DEBUG)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        debug_logger = DebugLogger(logger, func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            token = debug_logger_context.set(debug_logger)

            arg_summary = create_arg_summary(args, kwargs)
            debug_logger.debug(f"Enter with args: {arg_summary}")
            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                end_time = time.perf_counter()
                duration = end_time - start_time
                debug_logger.debug(f"Exit (duration: {duration:.6f}s)")
                return result
            except Exception as e:
                end_time = time.perf_counter()
                duration = end_time - start_time
                debug_logger.debug(f"Exit (duration: {duration:.6f}s), with error: {e}")
                raise
            finally:
                debug_logger_context.reset(token)

        return wrapper

    return decorator


def debug_logger():
    return debug_logger_context.get()


def create_arg_summary(args: tuple, kwargs: dict) -> str:
    MAX_ARG_LENGTH = 200
    MAX_TOTAL_LENGTH = 1000

    def stringify(arg):
        try:
            if isinstance(arg, BaseModel):
                return json.dumps(arg.model_dump())
            elif is_dataclass(arg):
                return json.dumps(asdict(arg))
            return json.dumps(arg)
        except:
            try:
                return str(arg)
            except:
                try:
                    return repr(arg)
                except:
                    return "<<unstringifiable>>"

    def trim_arg(arg_str: str, max_length: int) -> str:
        if len(arg_str) > max_length:
            return arg_str[:max_length] + "..."
        return arg_str

    arg_list = [trim_arg(stringify(arg), MAX_ARG_LENGTH) for arg in args]
    kwarg_list = [
        f"{k}={trim_arg(stringify(v), MAX_ARG_LENGTH)}" for k, v in kwargs.items()
    ]

    all_args = arg_list + kwarg_list
    summary = ", ".join(all_args)

    if len(summary) > MAX_TOTAL_LENGTH:
        return summary[:MAX_TOTAL_LENGTH] + "..."

    return summary
