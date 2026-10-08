"""Real Redis admission and ClickHouse orphan discovery."""

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
import redis

from weave.trace_server import export
from weave.trace_server import export_admission as admission
from weave.trace_server.project_version.types import ReadTable


def query_client(*counts):
    client = MagicMock()
    if counts:
        client.query.side_effect = [
            MagicMock(result_rows=[(count,)]) for count in counts
        ]
    else:
        client.query.return_value.result_rows = [(0,)]
    return client


def abandon(guard, redis_client):
    guard._stop.set()
    guard._heartbeat.join()
    redis_client.pexpire(admission.LEASE_KEY, 1)
    deadline = time.monotonic() + 1
    while redis_client.exists(admission.LEASE_KEY):
        assert time.monotonic() < deadline
        time.sleep(0.005)


def test_only_one_replica_can_claim_global_slot(export_redis):
    barrier = threading.Barrier(8)

    def acquire(index):
        barrier.wait()
        try:
            return admission.acquire_export_admission(query_client(), str(index), None)
        except admission.AdmissionError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=8) as pool:
        guards = list(pool.map(acquire, range(8)))
    winners = [
        guard for guard in guards if isinstance(guard, admission.ExportAdmission)
    ]
    failures = [
        guard for guard in guards if isinstance(guard, admission.AdmissionError)
    ]
    assert [(exc.http_status, exc.code) for exc in failures] == [
        (409, "EXPORT_BUSY")
    ] * 7
    assert len(winners) == 1
    winners[0].close(completed=True)
    assert export_redis.mget(admission.LEASE_KEY, admission.ACTIVE_KEY) == [None, None]


@pytest.mark.parametrize("counts", [(1,), (0, 0)])
def test_expired_lease_keeps_running_or_unknown_query_blocked(export_redis, counts):
    old = admission.acquire_export_admission(query_client(), "old", None)
    old.prepare_query(admission.export_query_id("old", "calls"))
    abandon(old, export_redis)
    with pytest.raises(admission.AdmissionError) as exc:
        admission.acquire_export_admission(query_client(*counts), "new", None)
    assert (exc.value.http_status, exc.value.code) == (409, "EXPORT_BUSY")
    assert json.loads(export_redis.get(admission.ACTIVE_KEY)) == {
        "job_id": "old",
        "query_id": "weave-export:old:calls",
    }


def test_completed_orphan_is_recovered_by_next_request(export_redis):
    old = admission.acquire_export_admission(query_client(), "old", None)
    old.prepare_query(admission.export_query_id("old", "calls"))
    abandon(old, export_redis)
    new = admission.acquire_export_admission(query_client(0, 1), "new", None)
    try:
        assert json.loads(export_redis.get(admission.ACTIVE_KEY)) == {
            "job_id": "new",
            "query_id": "",
        }
        with pytest.raises(admission.AdmissionError) as exc:
            old.prepare_query(admission.export_query_id("old", "objects"))
        assert exc.value.code == "EXPORT_LEASE_LOST"
        old.close(completed=True)
        assert export_redis.get(admission.LEASE_KEY) == "new"
    finally:
        new.close(completed=True)


def test_expired_owner_before_first_submission_cannot_submit(export_redis):
    old = admission.acquire_export_admission(query_client(), "old", None)
    abandon(old, export_redis)
    new = admission.acquire_export_admission(query_client(), "new", None)
    try:
        with pytest.raises(admission.AdmissionError, match="no longer owns"):
            old.prepare_query(admission.export_query_id("old", "calls"))
    finally:
        new.close(completed=True)


def test_failed_cluster_check_preserves_pending_intent(export_redis):
    old = admission.acquire_export_admission(query_client(), "old", None)
    old.prepare_query(admission.export_query_id("old", "calls"))
    abandon(old, export_redis)
    client = query_client()
    client.query.side_effect = RuntimeError("replica unavailable")
    with pytest.raises(admission.AdmissionError) as exc:
        admission.acquire_export_admission(client, "new", "replicas")
    assert (exc.value.http_status, exc.value.code) == (
        503,
        "EXPORT_ADMISSION_UNAVAILABLE",
    )
    assert export_redis.get(admission.ACTIVE_KEY) == old.record
    assert client.query.call_args.kwargs["settings"]["skip_unavailable_shards"] == 0


def test_missing_redis_fails_closed(monkeypatch):
    monkeypatch.setattr(admission, "get_redis_client", lambda: None)
    with pytest.raises(admission.AdmissionError) as exc:
        admission.acquire_export_admission(query_client(), "job", None)
    assert exc.value.code == "EXPORT_ADMISSION_UNAVAILABLE"


def test_renewal_keeps_live_owner_and_detects_replacement(export_redis, monkeypatch):
    monkeypatch.setattr(admission, "LEASE_SECONDS", 1)
    monkeypatch.setattr(admission, "RENEW_SECONDS", 0.02)
    guard = admission.acquire_export_admission(query_client(), "old", None)
    try:
        time.sleep(1.1)
        assert export_redis.get(admission.LEASE_KEY) == "old"
        export_redis.set(admission.LEASE_KEY, "replacement", ex=1)
        assert guard._lost.wait(1)
        with pytest.raises(admission.AdmissionError) as exc:
            guard.prepare_query(admission.export_query_id("old", "calls"))
        assert exc.value.code == "EXPORT_LEASE_LOST"
        guard.close(completed=True)
        assert export_redis.get(admission.LEASE_KEY) == "replacement"
    finally:
        guard.close(completed=False)


def test_busy_other_project_never_counts_writes_or_submits(export_redis, monkeypatch):
    guard = admission.acquire_export_admission(query_client(), "first", None)
    store = MagicMock()
    monkeypatch.setattr(export, "store_in_bucket", store)
    ch = query_client()
    try:
        with pytest.raises(export.ExportError) as exc:
            export.start_export(
                lambda: ch,
                MagicMock(),
                "other-project",
                ["calls"],
                ReadTable.CALLS_COMPLETE,
            )
        assert (exc.value.http_status, exc.value.code) == (409, "EXPORT_BUSY")
        ch.query.assert_not_called()
        ch.command.assert_not_called()
        store.assert_not_called()
    finally:
        guard.close(completed=True)


def test_redis_failure_does_not_submit_export(monkeypatch):
    client = MagicMock()
    client.set.side_effect = redis.ConnectionError("unavailable")
    monkeypatch.setattr(admission, "get_redis_client", lambda: client)
    ch = query_client()
    with pytest.raises(export.ExportError) as exc:
        export.start_export(
            lambda: ch, MagicMock(), "project", ["calls"], ReadTable.CALLS_COMPLETE
        )
    assert (exc.value.http_status, exc.value.code) == (
        503,
        "EXPORT_ADMISSION_UNAVAILABLE",
    )
    ch.command.assert_not_called()


def test_unknown_command_outcome_stops_remaining_targets(export_redis):
    ch = query_client()
    ch.command.side_effect = TimeoutError("connection lost")
    guard = admission.acquire_export_admission(ch, "job", None)
    export._run_export(
        ch,
        "project",
        "job",
        export._resolve_targets(["calls", "objects"], ReadTable.CALLS_COMPLETE),
        guard,
    )
    assert ch.command.call_count == 1
    assert json.loads(export_redis.get(admission.ACTIVE_KEY)) == {
        "job_id": "job",
        "query_id": "weave-export:job:calls",
    }


def test_real_clickhouse_query_outlives_owner_lease(export_redis, ch_server):
    client = ch_server._mint_client()
    job = str(uuid.uuid4())
    guard = admission.acquire_export_admission(client, job, None)
    qid = admission.export_query_id(job, "calls")
    guard.prepare_query(qid)
    errors = []

    def run():
        try:
            ch_server._mint_client().command(
                "SELECT sleep(2)", settings={"query_id": qid}
            )
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    try:
        deadline = time.monotonic() + 2
        while not admission.has_running_exports(client, None):
            assert time.monotonic() < deadline
            time.sleep(0.01)
        abandon(guard, export_redis)
        with pytest.raises(admission.AdmissionError) as exc:
            admission.acquire_export_admission(client, str(uuid.uuid4()), None)
        assert exc.value.code == "EXPORT_BUSY"
        worker.join()
        assert errors == []
        client.command("SYSTEM FLUSH LOGS")
        replacement = admission.acquire_export_admission(
            client, str(uuid.uuid4()), None
        )
        replacement.close(completed=True)
        assert export_redis.mget(admission.LEASE_KEY, admission.ACTIVE_KEY) == [
            None,
            None,
        ]
    finally:
        worker.join()
        guard.close(completed=False)
