import datetime
import re
from typing import Optional

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
    caplog, match_string: Optional[str] = None, getattrs: list[str] = ["msg"]
):
    """
    Get all log lines from caplog that match the given string.

    Match string is compared to the message, and getattrs is a list of attributes to get from the record.

    Example:
    ```python
    logger.info("my query", query="SELECT * FROM my_table")
    ```

    >>> get_info_loglines(caplog, "my query", ["msg", "query"])
    >>> [{"msg": "my query", "query": "SELECT * FROM my_table"}]
    """
    lines = []
    for record in caplog.records:
        if match_string and record.msg != match_string:
            continue
        line = {}
        for attr in getattrs:
            line[attr] = getattr(record, attr)
        lines.append(line)
    return lines
