from __future__ import annotations

import datetime
import io
import logging
import re
import time
from collections.abc import Callable
from contextlib import contextmanager

from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def client_is_sqlite(client):
    return isinstance(
        client.server._next_trace_server._internal_trace_server,
        SqliteTraceServer,
    )


class AnyStrMatcher:
    """Matches any string."""

    def __eq__(self, other):
        return isinstance(other, str)


class AnyIntMatcher:
    """Matches any integer."""

    def __eq__(self, other):
        return isinstance(other, int)


class RegexStringMatcher(str):
    """Matches strings based on a regex pattern."""

    def __init__(self, pattern):
        self.pattern = pattern

    def __eq__(self, other_string):
        if not isinstance(other_string, str):
            return NotImplemented
        return bool(re.match(self.pattern, other_string))


class MaybeStringMatcher:
    """Matches strings or None."""

    def __init__(self, s):
        self.s = s

    def __eq__(self, other):
        if other is None:
            return True
        return self.s == other


class FuzzyDateTimeMatcher:
    """Matches datetime objects within 1ms."""

    def __init__(self, dt):
        self.dt = dt

    def __eq__(self, other):
        # Checks within 1ms
        return abs((self.dt - other).total_seconds()) < 0.001


class DatetimeMatcher:
    def __eq__(self, other):
        return isinstance(other, datetime.datetime)


class DummyTestException(Exception):
    pass


def get_info_loglines(
    caplog, match_string: str | None = None, getattrs: list[str] | None = None
):
    """Get all log lines from caplog that match the given string.

    Match string is compared to the message, and getattrs is a list of attributes to get from the record.

    Example:
    ```python
    logger.info("my query", query="SELECT * FROM my_table")
    ```

    >>> get_info_loglines(caplog, "my query", ["msg", "query"])
    >>> [{"msg": "my query", "query": "SELECT * FROM my_table"}]
    """
    if getattrs is None:
        getattrs = ["msg"]

    lines = []
    for record in caplog.records:
        if match_string and record.msg != match_string:
            continue
        line = {}
        for attr in getattrs:
            line[attr] = getattr(record, attr)
        lines.append(line)
    return lines


@contextmanager
def capture_output(callbacks: list[Callable[[], None]]):
    captured_logs = io.StringIO()

    # Store original logging configuration
    old_handlers = logging.getLogger().handlers[:]
    old_level = logging.getLogger().level
    weave_logger = logging.getLogger("weave")
    old_weave_handlers = weave_logger.handlers[:]
    old_weave_level = weave_logger.level
    old_weave_propagate = weave_logger.propagate

    # Create a new handler for capturing logs
    log_handler = logging.StreamHandler(captured_logs)
    log_handler.setFormatter(logging.Formatter("%(message)s"))

    # Capture both root and weave-prefixed logger output for deterministic tests.
    root_logger = logging.getLogger()
    root_logger.handlers = [log_handler]
    root_logger.setLevel(logging.INFO)
    weave_logger.handlers = [log_handler]
    weave_logger.setLevel(logging.INFO)
    weave_logger.propagate = False

    try:
        yield captured_logs
    except DummyTestException:
        pass
    finally:
        for callback in callbacks:
            callback()
        root_logger.handlers = old_handlers
        root_logger.setLevel(old_level)
        weave_logger.handlers = old_weave_handlers
        weave_logger.setLevel(old_weave_level)
        weave_logger.propagate = old_weave_propagate


def flushing_callback(client):
    def _callback():
        client.future_executor.flush()
        time.sleep(0.01)  # Ensure on_finish_callback has time to fire post-flush

    return _callback
