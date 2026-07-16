"""Unit tests for the export Redis concurrency guard."""

from unittest.mock import MagicMock

import pytest

from weave.trace_server import export, export_rate_limit
from weave.trace_server.project_version.types import ReadTable


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        assert nx is True
        assert ex == export_rate_limit.EXPORT_LOCK_TTL_SECONDS
        if key in self.values:
            return False
        self.values[key] = value
        return True

    def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        assert script == export_rate_limit._RELEASE_IF_OWNED
        assert numkeys == 1
        if self.values.get(key) != token:
            return 0
        del self.values[key]
        return 1


def test_export_slot_limits_one_user_and_fails_closed_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = _FakeRedis()
    monkeypatch.setattr(export_rate_limit, "get_redis_client", lambda: redis)
    first_slot = export_rate_limit.acquire_export_slot("user-1")
    second_user_slot = export_rate_limit.acquire_export_slot("user-2")
    assert second_user_slot.key != first_slot.key

    with pytest.raises(export_rate_limit.ExportRateLimitError) as exc_info:
        export_rate_limit.acquire_export_slot("user-1")
    assert (exc_info.value.http_status, exc_info.value.code) == (
        409,
        "EXPORT_ALREADY_RUNNING",
    )

    # An expired lock may already have a new owner; old cleanup must not delete it.
    redis.values[first_slot.key] = "new-owner"
    export_rate_limit.release_export_slot(first_slot)
    assert redis.values[first_slot.key] == "new-owner"
    del redis.values[first_slot.key]
    assert export_rate_limit.acquire_export_slot("user-1").key == first_slot.key

    monkeypatch.setattr(export_rate_limit, "get_redis_client", lambda: None)
    with pytest.raises(export_rate_limit.ExportRateLimitError) as unavailable:
        export_rate_limit.acquire_export_slot("user-3")
    assert (unavailable.value.http_status, unavailable.value.code) == (
        503,
        "EXPORT_LIMIT_UNAVAILABLE",
    )


def test_start_export_maps_limit_errors_to_export_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_limit_error(_wb_user_id: str) -> None:
        raise export_rate_limit.ExportRateLimitError(
            409, "EXPORT_ALREADY_RUNNING", "an export is already running for this user"
        )

    monkeypatch.setattr(export_rate_limit, "acquire_export_slot", _raise_limit_error)
    with pytest.raises(export.ExportError) as exc_info:
        export.start_export(
            MagicMock(),
            MagicMock(),
            MagicMock(),
            "project",
            ["calls"],
            ReadTable.CALLS_COMPLETE,
            "user",
        )
    assert (exc_info.value.http_status, exc_info.value.code) == (
        409,
        "EXPORT_ALREADY_RUNNING",
    )


def test_preflight_failure_releases_its_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _FakeRedis()
    monkeypatch.setattr(export_rate_limit, "get_redis_client", lambda: redis)

    with pytest.raises(export.ExportError) as exc_info:
        export.start_export(
            MagicMock(),
            MagicMock(),
            None,
            "project",
            ["objects"],
            ReadTable.CALLS_COMPLETE,
            "user-1",
        )
    assert (exc_info.value.http_status, exc_info.value.code) == (
        503,
        "EXPORT_STORAGE_UNAVAILABLE",
    )
    assert export_rate_limit.acquire_export_slot("user-1").key


def test_worker_releases_its_slot_after_completion_or_startup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = _FakeRedis()
    monkeypatch.setattr(export_rate_limit, "get_redis_client", lambda: redis)

    # A target failure is recorded by query_log and must still free the user slot.
    first_slot = export_rate_limit.acquire_export_slot("user-1")
    command_client = MagicMock()
    command_client.command.side_effect = RuntimeError("target failed")
    export._run_export(
        lambda: command_client,
        "project",
        "job",
        [export.ResolvedExportTarget("objects", "SELECT 1")],
        first_slot,
    )
    assert first_slot.key not in redis.values

    # If the detached client cannot even start, its reservation still cannot leak.
    second_slot = export_rate_limit.acquire_export_slot("user-1")
    with pytest.raises(RuntimeError, match="client failed"):
        export._run_export(
            lambda: (_ for _ in ()).throw(RuntimeError("client failed")),
            "project",
            "job",
            [],
            second_slot,
        )
    assert second_slot.key not in redis.values
