"""Engine-level behavior.

Uses a fake CH client driven by a script (one stub return per CH call) so
the tests are deterministic and don't require a live ClickHouse. Real-CH
integration coverage lives in `tests/trace_server_migrator/` and (when
spun up) the export integration shard.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest
from pydantic import SecretStr

from weave.trace_server.byob.resolver import (
    BYOBResolver,
    ExportStorageCredentials,
    ResolvedExportTarget,
    StorageResolutionError,
)
from weave.trace_server.export import constants
from weave.trace_server.export.engine import (
    ConcurrentExportLimitError,
    ExportEngine,
    ExportTooLargeError,
    RequestTooLargeError,
)
from weave.trace_server.export.schemas import ExportStartReq

PROJECT = "UHJvajEyMw=="


def _make_target(project_id: str = PROJECT) -> ResolvedExportTarget:
    return ResolvedExportTarget(
        bucket_uri="s3://team-bucket",
        bucket_name="team-bucket",
        region="us-west-2",
        credentials=ExportStorageCredentials(
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
            session_token=SecretStr("FQoGZXIvYXdzEPL"),
        ),
        source_project_id=project_id,
    )


class _FakeResolver(BYOBResolver):
    """Engine-only fake: only `resolve_export_target` is exercised here.

    The file-storage methods (`resolve_write`, `resolve_read`) are
    irrelevant to the export path; they raise to make accidental use
    visible.
    """

    def __init__(self, target: ResolvedExportTarget | None = None) -> None:
        self._target = target
        self.calls: list[str] = []

    def resolve_write(self, project_id, default_client):  # pragma: no cover
        raise AssertionError("export engine must not call resolve_write")

    def resolve_read(self, project_id, stored_uri, default_client):  # pragma: no cover
        raise AssertionError("export engine must not call resolve_read")

    def resolve_export_target(self, project_id: str) -> ResolvedExportTarget:
        self.calls.append(project_id)
        if self._target is None:
            raise StorageResolutionError("no bucket configured")
        return self._target


@dataclass
class _QueryResult:
    """Mirrors the slice of clickhouse_connect.QueryResult the engine uses."""

    result_rows: list[tuple[Any, ...]]


class _FakeClient:
    """Drives `query`/`command` from a per-test script.

    Each `query()` call pops one row-set from `query_returns`; each
    `command()` and `insert()` call appends to `commands` / `inserts` for
    later assertions.
    """

    def __init__(self) -> None:
        self.query_returns: list[list[tuple[Any, ...]]] = []
        self.commands: list[tuple[str, dict[str, Any] | None]] = []
        self.inserts: list[tuple[str, list[tuple[object, ...]], list[str]]] = []

    def query(self, sql: str, parameters: dict[str, Any] | None = None) -> _QueryResult:
        rows = self.query_returns.pop(0)
        return _QueryResult(result_rows=rows)

    def command(self, cmd: str, *, parameters=None, settings=None) -> None:
        self.commands.append((cmd, settings))

    def insert(
        self, table: str, rows: list[tuple[object, ...]], *, column_names: list[str]
    ) -> None:
        self.inserts.append((table, rows, column_names))


@pytest.fixture
def fake_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    return now


def _build_engine(client: _FakeClient, resolver: BYOBResolver) -> ExportEngine:
    return ExportEngine(client, resolver, env="test")


def test_start_happy_path_submits_create_then_insert_and_audits() -> None:
    client = _FakeClient()
    # concurrent count -> 0; preflight count -> 100.
    client.query_returns = [[(0,)], [(100,)]]
    resolver = _FakeResolver(_make_target())

    e = _build_engine(client, resolver)
    res = e.start(
        ExportStartReq(project_id=PROJECT, table="calls_complete"),
        requested_by="user-a",
    )

    assert isinstance(res.job_id, UUID)
    # commands fired: DROP -> CREATE -> INSERT
    cmd_texts = [c[0] for c in client.commands]
    assert any("DROP NAMED COLLECTION" in c for c in cmd_texts)
    assert any("CREATE NAMED COLLECTION" in c for c in cmd_texts)
    assert any("INSERT INTO FUNCTION s3" in c for c in cmd_texts)
    # CREATE+DROP suppressed from query_log via settings
    for cmd, settings in client.commands:
        if "NAMED COLLECTION" in cmd:
            assert settings == {"log_queries": "0"}
        if cmd.startswith("INSERT"):
            assert settings is not None
            assert settings["query_id"] == str(res.job_id)
            assert settings["wait_end_of_query"] == "0"
    # one audit row written
    assert len(client.inserts) == 1
    table_name, rows, cols = client.inserts[0]
    assert table_name == "exports"
    assert "action" in cols
    inserted_action = rows[0][cols.index("action")]
    assert inserted_action == "EXPORT_START"


def test_no_storage_target_propagates_resolution_error() -> None:
    client = _FakeClient()
    client.query_returns = [[(0,)], [(100,)]]
    resolver = _FakeResolver(target=None)

    e = _build_engine(client, resolver)
    with pytest.raises(StorageResolutionError):
        e.start(
            ExportStartReq(project_id=PROJECT, table="calls_complete"),
            requested_by="user-a",
        )
    # no NC was created, no audit row written
    assert client.commands == []
    assert client.inserts == []


def test_too_large_raises_before_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(constants, "PHASE_2_PARTITION_ROW_THRESHOLD", 10)
    client = _FakeClient()
    client.query_returns = [[(0,)], [(11,)]]
    resolver = _FakeResolver(_make_target())

    e = _build_engine(client, resolver)
    with pytest.raises(ExportTooLargeError) as exc_info:
        e.start(
            ExportStartReq(project_id=PROJECT, table="calls_complete"),
            requested_by="user-a",
        )
    assert exc_info.value.row_count == 11
    assert resolver.calls == []  # never reached the resolver
    assert client.inserts == []


def test_concurrent_cap_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(constants, "MAX_CONCURRENT_EXPORTS_PER_PROJECT", 1)
    client = _FakeClient()
    client.query_returns = [[(1,)]]  # in-flight count already at the cap
    resolver = _FakeResolver(_make_target())

    e = _build_engine(client, resolver)
    with pytest.raises(ConcurrentExportLimitError):
        e.start(
            ExportStartReq(project_id=PROJECT, table="calls_complete"),
            requested_by="user-a",
        )
    assert client.commands == []
    assert client.inserts == []


def test_oversized_request_json_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(constants, "MAX_REQUEST_JSON_BYTES", 4)
    client = _FakeClient()
    resolver = _FakeResolver(_make_target())

    e = _build_engine(client, resolver)
    with pytest.raises(RequestTooLargeError):
        e.start(
            ExportStartReq(project_id=PROJECT, table="calls_complete"),
            requested_by="user-a",
        )
    # request size guard fires before any CH interaction
    assert client.commands == []
    assert client.inserts == []
    assert client.query_returns == []


class _RaisingOnInsertClient(_FakeClient):
    """Fake CH client whose first INSERT raises mid-submission."""

    def __init__(self) -> None:
        super().__init__()
        self._first_insert = True

    def command(self, cmd: str, *, parameters=None, settings=None) -> None:
        if cmd.startswith("INSERT") and self._first_insert:
            self._first_insert = False
            super().command(cmd, parameters=parameters, settings=settings)
            raise RuntimeError("ch unavailable")
        super().command(cmd, parameters=parameters, settings=settings)


def test_insert_failure_drops_named_collection_on_failure() -> None:
    """Submit failure must DROP the NC so plaintext STS creds don't linger."""
    client = _RaisingOnInsertClient()
    client.query_returns = [[(0,)], [(50,)]]
    resolver = _FakeResolver(_make_target())

    e = _build_engine(client, resolver)
    with pytest.raises(RuntimeError, match="ch unavailable"):
        e.start(
            ExportStartReq(project_id=PROJECT, table="calls_complete"),
            requested_by="user-a",
        )

    drops = [c for c, _ in client.commands if c.startswith("DROP NAMED COLLECTION")]
    assert len(drops) == 2, drops  # DROP at start + DROP in cleanup


@pytest.mark.disable_logging_error_check
def test_resolver_target_mismatch_refuses_to_proceed() -> None:
    """Defense-in-depth: target.source_project_id must match request."""
    client = _FakeClient()
    client.query_returns = [[(0,)], [(50,)]]
    # Resolver returns a target keyed to a DIFFERENT project_id.
    resolver = _FakeResolver(_make_target(project_id="OTHER_PROJECT"))

    e = _build_engine(client, resolver)
    with pytest.raises(StorageResolutionError, match="does not match"):
        e.start(
            ExportStartReq(project_id=PROJECT, table="calls_complete"),
            requested_by="user-a",
        )
    # No NC created, no audit row written.
    assert client.commands == []
    assert client.inserts == []
