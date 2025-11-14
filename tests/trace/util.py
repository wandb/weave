from __future__ import annotations

import datetime
import io
import logging
import re
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from weave.trace.refs import ObjectRef, OpRef, Ref
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


class ObjectRefStrMatcher:
    def __init__(
        self,
        entity: str | None = None,
        project: str | None = None,
        kind: str | None = None,
        name: str | None = None,
        digest: str | None = None,
        extra: list[str] | None = None,
    ) -> None:
        self.entity = entity
        self.project = project
        self.kind = kind
        self.name = name
        self.digest = digest
        self.extra = extra

    def __eq__(self, other: Any) -> bool:
        other_ref = Ref.parse_uri(other)
        if not isinstance(other_ref, ObjectRef):
            return False
        if self.entity is not None and self.entity != other_ref.entity:
            return False
        if self.project is not None and self.project != other_ref.project:
            return False
        if self.kind is not None:
            if isinstance(other_ref, ObjectRef):
                other_kind = "object"
            elif isinstance(other_ref, OpRef):
                other_kind = "op"
            else:
                raise ValueError(f"Unknown kind: {other_ref}")
            if self.kind != other_kind:
                return False
        if self.name is not None and self.name != other_ref.name:
            return False
        if self.digest is not None and self.digest != other_ref.digest:
            return False
        if self.extra is not None and self.extra != other_ref.extra:
            return False
        return True


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

    # Store original stdout and logging handlers
    old_handlers = logging.getLogger().handlers[:]

    # Create a new handler for capturing logs
    log_handler = logging.StreamHandler(captured_logs)
    log_handler.setFormatter(logging.Formatter("%(message)s"))

    # Replace stdout and logging handlers
    root_logger = logging.getLogger()
    root_logger.handlers = [log_handler]

    try:
        yield captured_logs
    except DummyTestException:
        pass
    finally:
        for callback in callbacks:
            callback()
        root_logger.handlers = old_handlers


def flushing_callback(client):
    def _callback():
        client.future_executor.flush()
        time.sleep(0.01)  # Ensure on_finish_callback has time to fire post-flush

    return _callback
