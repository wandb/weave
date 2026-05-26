"""Sweeper drop-decision behavior.

Drives `_should_drop` with a fake CH client whose query/command results are
scripted per call. Covers the three branches: query_log row present and
terminal, query_log missing but audit row past budget, audit row also
missing entirely.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from weave.trace_server.export import sweeper
from weave.trace_server.export.constants import MAX_EXPORT_QUERY_SECONDS


@dataclass
class _QueryResult:
    result_rows: list[tuple[Any, ...]]


class _FakeClient:
    """Scripts replies for `_should_drop` and `sweep_orphan_named_collections`.

    `query_returns` queue is consumed in FIFO order across both the
    `system.query_log` lookup AND the audit `exports` lookup that follows
    when query_log returns no row.
    """

    def __init__(self) -> None:
        self.query_returns: list[list[tuple[Any, ...]]] = []
        self.commands: list[tuple[str, dict[str, Any] | None]] = []

    def query(self, sql: str, parameters: dict[str, Any] | None = None) -> _QueryResult:
        return _QueryResult(result_rows=self.query_returns.pop(0))

    def command(self, cmd: str, *, parameters=None, settings=None) -> None:
        self.commands.append((cmd, settings))


def _job() -> UUID:
    return uuid4()


def test_should_drop_when_query_log_reports_terminal() -> None:
    client = _FakeClient()
    client.query_returns = [
        [("QueryFinish", 0, "", 1000, 50_000)],  # query_log terminal-success row
    ]
    assert sweeper._should_drop(client, _job()) is True


def test_should_not_drop_when_query_log_reports_running() -> None:
    client = _FakeClient()
    client.query_returns = [
        [("QueryStart", 0, "", 0, 0)],  # still running
    ]
    assert sweeper._should_drop(client, _job()) is False


def test_should_drop_when_audit_row_past_budget_and_query_log_missing() -> None:
    """No query_log row, audit row older than MAX_EXPORT_QUERY_SECONDS + grace."""
    client = _FakeClient()
    submitted = datetime.now(timezone.utc) - timedelta(
        seconds=MAX_EXPORT_QUERY_SECONDS + 600
    )
    client.query_returns = [
        [],  # query_log: no row
        [("p1", "user-a", "calls_complete", submitted)],  # audit lookup
    ]
    assert sweeper._should_drop(client, _job()) is True


def test_should_not_drop_when_audit_row_inside_budget_and_query_log_missing() -> None:
    """Recent audit submission, query_log not flushed yet: leave NC alone."""
    client = _FakeClient()
    submitted = datetime.now(timezone.utc) - timedelta(seconds=30)
    client.query_returns = [
        [],  # query_log: no row
        [("p1", "user-a", "calls_complete", submitted)],
    ]
    assert sweeper._should_drop(client, _job()) is False


def test_should_drop_when_query_log_and_audit_both_missing() -> None:
    """Engine crashed between CREATE NC and audit write -> orphan NC."""
    client = _FakeClient()
    client.query_returns = [
        [],  # query_log: no row
        [],  # audit: no row
    ]
    assert sweeper._should_drop(client, _job()) is True


def test_sweep_drops_terminal_nc_and_skips_unparseable_name() -> None:
    """End-to-end sweep over a list of NCs from system.named_collections."""
    client = _FakeClient()
    nc_terminal = "export_" + uuid4().hex
    nc_garbage = "export_not-a-uuid"
    client.query_returns = [
        [(nc_terminal,), (nc_garbage,)],  # scan result
        [("QueryFinish", 0, "", 1000, 50_000)],  # terminal NC's query_log row
    ]
    dropped = sweeper.sweep_orphan_named_collections(client)
    assert dropped == 1
    drop_cmds = [c for c, _ in client.commands if c.startswith("DROP NAMED COLLECTION")]
    assert len(drop_cmds) == 1
    assert nc_terminal.split("_", 1)[1] in drop_cmds[0]


def test_job_id_from_nc_name_rejects_bad_input() -> None:
    assert sweeper._job_id_from_nc_name("not_prefixed") is None
    assert sweeper._job_id_from_nc_name("export_") is None
    assert sweeper._job_id_from_nc_name("export_not-a-uuid") is None
    valid = uuid4()
    assert sweeper._job_id_from_nc_name(f"export_{valid.hex}") == valid
