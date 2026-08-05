from __future__ import annotations

import hashlib
import sqlite3
import stat
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from weave.trace_server.agents.historical_turn_validation import (
    HistoricalTurnCapabilityMismatchError,
    HistoricalTurnValidationError,
    compute_historical_turn_child_span_id,
    compute_historical_turn_logical_key,
    compute_historical_turn_payload_sizes,
    compute_historical_turn_root_span_id,
    compute_historical_turn_trace_id,
    compute_historical_turn_wire_sha256,
)
from weave.trace_server.agents.types import (
    HistoricalTurnCapabilitiesReq,
    HistoricalTurnSpan,
    HistoricalTurnStatusReq,
    HistoricalTurnUpsertReq,
    PreparedTurn,
)
from weave.trace_server.historical_turns import (
    HistoricalTurnCommitError,
    HistoricalTurnService,
    HistoricalTurnStoredRow,
    HistoricalTurnWriterResult,
    SQLiteHistoricalTurnCommitStore,
    SQLiteHistoricalTurnWriter,
)

PROJECT_ID = "entity/historical"
CONVERSATION_ID = "hivemind:session-1"
TURN_KEY = "turn-0001"


class BlockingCASWriter:
    def __init__(self, writer: SQLiteHistoricalTurnWriter) -> None:
        self.writer = writer
        self.first_row_visible = threading.Event()
        self.release_first_caller = threading.Event()

    def put_if_absent(self, **kwargs) -> HistoricalTurnWriterResult:
        result = self.writer.put_if_absent(**kwargs)
        if result.outcome == "created":
            self.first_row_visible.set()
            if not self.release_first_caller.wait(timeout=5):
                raise TimeoutError("test did not release first CAS caller")
        return result

    def get_existing(self, **kwargs) -> HistoricalTurnStoredRow | None:
        return self.writer.get_existing(**kwargs)


class FailFirstJournalCommitStore(SQLiteHistoricalTurnCommitStore):
    def __init__(self, path) -> None:
        super().__init__(path)
        self.fail_next_commit = True

    def mark_committed(self, **kwargs):
        if self.fail_next_commit:
            self.fail_next_commit = False
            raise RuntimeError("simulated process exit before journal commit")
        return super().mark_committed(**kwargs)


def _prepared_turn(payload: str = "first") -> PreparedTurn:
    logical_key = compute_historical_turn_logical_key(
        PROJECT_ID, CONVERSATION_ID, TURN_KEY
    )
    source_payload_sha256 = hashlib.sha256(payload.encode()).hexdigest()
    trace_id = compute_historical_turn_trace_id(logical_key)
    root_span_id = compute_historical_turn_root_span_id(logical_key)
    child_span_id = compute_historical_turn_child_span_id(logical_key, 0, "tool")
    spans = [
        HistoricalTurnSpan(
            kind="turn",
            name="invoke_agent codex",
            trace_id=trace_id,
            span_id=root_span_id,
            start_time_unix_nano=100,
            end_time_unix_nano=400,
            attributes={
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.conversation.id": CONVERSATION_ID,
                "fixture.payload": payload,
                "historical_turn.logical_key": logical_key,
                "historical_turn.turn_key": TURN_KEY,
                "historical_turn.source_payload_sha256": source_payload_sha256,
                "historical_turn.schema_version": "1",
            },
        ),
        HistoricalTurnSpan(
            kind="tool",
            name="execute_tool shell",
            trace_id=trace_id,
            span_id=child_span_id,
            parent_span_id=root_span_id,
            start_time_unix_nano=200,
            end_time_unix_nano=300,
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.conversation.id": CONVERSATION_ID,
            },
        ),
    ]
    provisional = PreparedTurn(
        logical_key=logical_key,
        turn_key=TURN_KEY,
        source_payload_sha256=source_payload_sha256,
        wire_sha256="0" * 64,
        compressed_bytes=0,
        uncompressed_bytes=0,
        destination_project_id=PROJECT_ID,
        conversation_id=CONVERSATION_ID,
        trace_id=trace_id,
        root_span_id=root_span_id,
        spans=spans,
        span_count=2,
    )
    compressed_bytes, uncompressed_bytes = compute_historical_turn_payload_sizes(
        provisional
    )
    sized = provisional.model_copy(
        update={
            "compressed_bytes": compressed_bytes,
            "uncompressed_bytes": uncompressed_bytes,
        }
    )
    return sized.model_copy(
        update={"wire_sha256": compute_historical_turn_wire_sha256(sized)}
    )


def _rehash(turn: PreparedTurn) -> PreparedTurn:
    provisional = turn.model_copy(
        update={
            "wire_sha256": "0" * 64,
            "compressed_bytes": 0,
            "uncompressed_bytes": 0,
        }
    )
    compressed_bytes, uncompressed_bytes = compute_historical_turn_payload_sizes(
        provisional
    )
    sized = provisional.model_copy(
        update={
            "compressed_bytes": compressed_bytes,
            "uncompressed_bytes": uncompressed_bytes,
        }
    )
    return sized.model_copy(
        update={"wire_sha256": compute_historical_turn_wire_sha256(sized)}
    )


def _service(tmp_path, *, store=None, writer=None):
    database_path = tmp_path / "turns.db"
    resolved_store = store or SQLiteHistoricalTurnCommitStore(database_path)
    resolved_writer = writer or SQLiteHistoricalTurnWriter(database_path)
    return (
        HistoricalTurnService(
            store=resolved_store,
            writer=resolved_writer,
            recovery_lease_seconds=1,
        ),
        resolved_store,
        resolved_writer,
    )


def test_identical_upsert_replays_and_status_has_exact_evidence(tmp_path) -> None:
    service, _, writer = _service(tmp_path)
    turn = _prepared_turn()
    request = HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)

    first = service.historical_turn_upsert(request)
    second = service.historical_turn_upsert(request)
    status = service.historical_turn_status(
        HistoricalTurnStatusReq(project_id=PROJECT_ID, logical_key=turn.logical_key)
    )

    assert first.model_dump() == {
        "logical_key": turn.logical_key,
        "wire_sha256": turn.wire_sha256,
        "status": "committed",
        "commit_id": first.commit_id,
        "storage_row_key": first.storage_row_key,
        "trace_ids": [turn.trace_id],
        "root_span_ids": [turn.root_span_id],
        "span_count": 2,
        "existing_wire_sha256": None,
    }
    assert second.model_dump() == {
        **first.model_dump(),
        "status": "replayed",
    }
    assert status.model_dump() == {
        "logical_key": turn.logical_key,
        "status": "committed",
        "wire_sha256": turn.wire_sha256,
        "commit_id": first.commit_id,
        "storage_row_key": first.storage_row_key,
        "trace_ids": [turn.trace_id],
        "root_span_ids": [turn.root_span_id],
        "span_count": 2,
        "last_error": None,
    }
    assert first.storage_row_key is not None
    assert writer.row_count(project_id=PROJECT_ID, logical_key=turn.logical_key) == 1
    assert writer.read(project_id=PROJECT_ID, logical_key=turn.logical_key) == turn


def test_changed_payload_for_same_key_is_conflict_without_second_write(
    tmp_path,
) -> None:
    service, _, writer = _service(tmp_path)
    first_turn = _prepared_turn("first")
    changed_turn = _prepared_turn("changed")
    service.historical_turn_upsert(
        HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=first_turn)
    )

    result = service.historical_turn_upsert(
        HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=changed_turn)
    )

    assert result.model_dump() == {
        "logical_key": changed_turn.logical_key,
        "wire_sha256": changed_turn.wire_sha256,
        "status": "conflict",
        "commit_id": None,
        "storage_row_key": None,
        "trace_ids": [],
        "root_span_ids": [],
        "span_count": 0,
        "existing_wire_sha256": first_turn.wire_sha256,
    }
    assert (
        writer.row_count(project_id=PROJECT_ID, logical_key=first_turn.logical_key) == 1
    )
    assert (
        writer.read(project_id=PROJECT_ID, logical_key=first_turn.logical_key)
        == first_turn
    )


def test_concurrent_identical_upserts_commit_one_complete_row(tmp_path) -> None:
    database_path = tmp_path / "turns.db"
    store = SQLiteHistoricalTurnCommitStore(database_path)
    real_writer = SQLiteHistoricalTurnWriter(database_path)
    blocking_writer = BlockingCASWriter(real_writer)
    first_service, _, _ = _service(tmp_path, store=store, writer=blocking_writer)
    second_service, _, _ = _service(tmp_path, store=store, writer=blocking_writer)
    turn = _prepared_turn()
    request = HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)

    with ThreadPoolExecutor(max_workers=1) as executor:
        first_future = executor.submit(first_service.historical_turn_upsert, request)
        assert blocking_writer.first_row_visible.wait(timeout=5)
        in_progress = second_service.historical_turn_upsert(request)
        blocking_writer.release_first_caller.set()
        committed = first_future.result(timeout=5)

    status = second_service.historical_turn_status(
        HistoricalTurnStatusReq(project_id=PROJECT_ID, logical_key=turn.logical_key)
    )
    assert in_progress.status == "committing"
    assert in_progress.commit_id == committed.commit_id
    assert in_progress.trace_ids == committed.trace_ids == [turn.trace_id]
    assert in_progress.root_span_ids == committed.root_span_ids == [turn.root_span_id]
    assert status.status == "committed"
    assert status.commit_id == committed.commit_id
    assert (
        real_writer.row_count(project_id=PROJECT_ID, logical_key=turn.logical_key) == 1
    )


def test_concurrent_different_payloads_commit_one_and_conflict_one(tmp_path) -> None:
    database_path = tmp_path / "turns.db"
    store = SQLiteHistoricalTurnCommitStore(database_path)
    real_writer = SQLiteHistoricalTurnWriter(database_path)
    blocking_writer = BlockingCASWriter(real_writer)
    first_service, _, _ = _service(tmp_path, store=store, writer=blocking_writer)
    second_service, _, _ = _service(tmp_path, store=store, writer=blocking_writer)
    first_turn = _prepared_turn("first")
    changed_turn = _prepared_turn("changed")

    with ThreadPoolExecutor(max_workers=1) as executor:
        first_future = executor.submit(
            first_service.historical_turn_upsert,
            HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=first_turn),
        )
        assert blocking_writer.first_row_visible.wait(timeout=5)
        conflict = second_service.historical_turn_upsert(
            HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=changed_turn)
        )
        blocking_writer.release_first_caller.set()
        committed = first_future.result(timeout=5)

    assert committed.status == "committed"
    assert conflict.status == "conflict"
    assert conflict.existing_wire_sha256 == first_turn.wire_sha256
    assert (
        real_writer.row_count(project_id=PROJECT_ID, logical_key=first_turn.logical_key)
        == 1
    )
    assert (
        real_writer.read(project_id=PROJECT_ID, logical_key=first_turn.logical_key)
        == first_turn
    )


def test_invalid_child_is_rejected_before_journal_or_writer(tmp_path) -> None:
    service, store, writer = _service(tmp_path)
    turn = _prepared_turn()
    bad_child = turn.spans[1].model_copy(update={"parent_span_id": "f" * 16})
    invalid_turn = _rehash(
        turn.model_copy(update={"spans": [turn.spans[0], bad_child]})
    )
    valid_request = HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)
    invalid_request = valid_request.model_copy(update={"turn": invalid_turn})

    with pytest.raises(
        HistoricalTurnValidationError,
        match=(r"(?s)historical turn envelope is structurally invalid: .*direct child"),
    ):
        service.historical_turn_upsert(invalid_request)

    assert writer.read(project_id=PROJECT_ID, logical_key=turn.logical_key) is None
    assert store.get(project_id=PROJECT_ID, logical_key=turn.logical_key) is None


def test_nondeterministic_ids_are_rejected_before_write(tmp_path) -> None:
    service, store, writer = _service(tmp_path)
    turn = _prepared_turn()
    forged_trace_id = "f" * 32
    forged_root_span_id = "e" * 16
    forged_spans = [
        turn.spans[0].model_copy(
            update={
                "trace_id": forged_trace_id,
                "span_id": forged_root_span_id,
            }
        ),
        turn.spans[1].model_copy(
            update={
                "trace_id": forged_trace_id,
                "span_id": "d" * 16,
                "parent_span_id": forged_root_span_id,
            }
        ),
    ]
    invalid_turn = _rehash(
        turn.model_copy(
            update={
                "trace_id": forged_trace_id,
                "root_span_id": forged_root_span_id,
                "spans": forged_spans,
            }
        )
    )

    with pytest.raises(
        HistoricalTurnValidationError,
        match="historical turn trace_id is not deterministic for its logical_key",
    ):
        service.historical_turn_upsert(
            HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=invalid_turn)
        )

    assert writer.read(project_id=PROJECT_ID, logical_key=turn.logical_key) is None
    assert store.get(project_id=PROJECT_ID, logical_key=turn.logical_key) is None


def test_root_certificate_is_bound_before_write(tmp_path) -> None:
    service, store, writer = _service(tmp_path)
    turn = _prepared_turn()
    root_attributes = dict(turn.spans[0].attributes)
    root_attributes["historical_turn.logical_key"] = "forged-search-value"
    forged_root = turn.spans[0].model_copy(update={"attributes": root_attributes})
    invalid_turn = _rehash(
        turn.model_copy(update={"spans": [forged_root, *turn.spans[1:]]})
    )

    with pytest.raises(
        HistoricalTurnValidationError,
        match=(
            "turn root attribute 'historical_turn.logical_key' does not match "
            "the envelope"
        ),
    ):
        service.historical_turn_upsert(
            HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=invalid_turn)
        )

    assert writer.read(project_id=PROJECT_ID, logical_key=turn.logical_key) is None
    assert store.get(project_id=PROJECT_ID, logical_key=turn.logical_key) is None


def test_destination_mismatch_is_rejected_before_write(tmp_path) -> None:
    service, store, writer = _service(tmp_path)
    turn = _prepared_turn()

    with pytest.raises(
        HistoricalTurnValidationError,
        match="historical turn destination project does not match the request project",
    ):
        service.historical_turn_upsert(
            HistoricalTurnUpsertReq(project_id="other/project", turn=turn)
        )

    assert writer.read(project_id="other/project", logical_key=turn.logical_key) is None
    assert store.get(project_id="other/project", logical_key=turn.logical_key) is None


def test_capability_mismatch_is_typed_and_rejected_before_write(tmp_path) -> None:
    service, store, writer = _service(tmp_path)
    turn = _prepared_turn()
    drifted = turn.model_copy(update={"capability_version": "historical-turn-v2"})
    request = HistoricalTurnUpsertReq(
        project_id=PROJECT_ID,
        capability_version="historical-turn-v2",
        turn=drifted,
    )

    with pytest.raises(
        HistoricalTurnCapabilityMismatchError,
        match=(
            "historical turn capability mismatch: expected 'historical-turn-v1', "
            "got request 'historical-turn-v2' and envelope 'historical-turn-v2'"
        ),
    ) as exc_info:
        service.historical_turn_upsert(request)

    assert exc_info.value.http_status_code == 412
    assert writer.read(project_id=PROJECT_ID, logical_key=turn.logical_key) is None
    assert store.get(project_id=PROJECT_ID, logical_key=turn.logical_key) is None


def test_retry_reconciles_writer_commit_after_journal_crash(tmp_path) -> None:
    store = FailFirstJournalCommitStore(tmp_path / "turns.db")
    writer = SQLiteHistoricalTurnWriter(tmp_path / "turns.db")
    service, _, _ = _service(tmp_path, store=store, writer=writer)
    turn = _prepared_turn()
    request = HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)

    with pytest.raises(
        RuntimeError, match="simulated process exit before journal commit"
    ):
        service.historical_turn_upsert(request)
    reconciled = service.historical_turn_status(
        HistoricalTurnStatusReq(project_id=PROJECT_ID, logical_key=turn.logical_key)
    )
    replay = service.historical_turn_upsert(request)

    assert reconciled.status == "committed"
    assert reconciled.last_error is None
    assert reconciled.trace_ids == [turn.trace_id]
    assert reconciled.root_span_ids == [turn.root_span_id]
    assert reconciled.storage_row_key is not None
    assert replay.status == "replayed"
    assert replay.trace_ids == [turn.trace_id]
    assert replay.root_span_ids == [turn.root_span_id]
    assert replay.storage_row_key == reconciled.storage_row_key
    assert writer.row_count(project_id=PROJECT_ID, logical_key=turn.logical_key) == 1
    assert writer.read(project_id=PROJECT_ID, logical_key=turn.logical_key) == turn


def test_status_get_never_creates_a_missing_storage_row(tmp_path) -> None:
    service, store, writer = _service(tmp_path)
    turn = _prepared_turn()
    claim = store.claim(project_id=PROJECT_ID, turn=turn, lease_seconds=1)

    status = service.historical_turn_status(
        HistoricalTurnStatusReq(project_id=PROJECT_ID, logical_key=turn.logical_key)
    )

    assert claim.outcome == "acquired"
    assert status.status == "committing"
    assert status.storage_row_key is None
    assert writer.row_count(project_id=PROJECT_ID, logical_key=turn.logical_key) == 0


def test_storage_cas_conflict_preserves_existing_complete_row(tmp_path) -> None:
    writer = SQLiteHistoricalTurnWriter(tmp_path / "turns.db")
    changed_turn = _prepared_turn("already-stored")
    stored = writer.put_if_absent(
        project_id=PROJECT_ID,
        logical_key=changed_turn.logical_key,
        wire_sha256=changed_turn.wire_sha256,
        complete_row=changed_turn,
        wb_user_id=None,
    )
    service, _, _ = _service(tmp_path, writer=writer)
    turn = _prepared_turn("new-payload")

    result = service.historical_turn_upsert(
        HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)
    )

    assert stored.outcome == "created"
    assert result.status == "conflict"
    assert result.storage_row_key == stored.storage_row_key
    assert result.existing_wire_sha256 == changed_turn.wire_sha256
    assert writer.row_count(project_id=PROJECT_ID, logical_key=turn.logical_key) == 1
    assert (
        writer.read(project_id=PROJECT_ID, logical_key=turn.logical_key) == changed_turn
    )
    status = service.historical_turn_status(
        HistoricalTurnStatusReq(
            project_id=PROJECT_ID,
            logical_key=turn.logical_key,
        )
    )
    replay = service.historical_turn_upsert(
        HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=changed_turn)
    )
    repeated_conflict = service.historical_turn_upsert(
        HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)
    )

    assert status.status == "committed"
    assert status.wire_sha256 == changed_turn.wire_sha256
    assert status.storage_row_key == stored.storage_row_key
    assert status.trace_ids == [changed_turn.trace_id]
    assert status.root_span_ids == [changed_turn.root_span_id]
    assert status.span_count == changed_turn.span_count
    assert replay.status == "replayed"
    assert replay.wire_sha256 == changed_turn.wire_sha256
    assert repeated_conflict.status == "conflict"
    assert repeated_conflict.existing_wire_sha256 == changed_turn.wire_sha256


def test_status_adopts_authoritative_storage_conflict_after_interruption(
    tmp_path,
) -> None:
    database_path = tmp_path / "turns.db"
    writer = SQLiteHistoricalTurnWriter(database_path)
    stored_turn = _prepared_turn("already-stored")
    stored = writer.put_if_absent(
        project_id=PROJECT_ID,
        logical_key=stored_turn.logical_key,
        wire_sha256=stored_turn.wire_sha256,
        complete_row=stored_turn,
        wb_user_id=None,
    )
    store = SQLiteHistoricalTurnCommitStore(database_path)
    interrupted_turn = _prepared_turn("interrupted-conflict")
    claim = store.claim(
        project_id=PROJECT_ID,
        turn=interrupted_turn,
        lease_seconds=30,
    )
    service, _, _ = _service(tmp_path, store=store, writer=writer)

    status = service.historical_turn_status(
        HistoricalTurnStatusReq(
            project_id=PROJECT_ID,
            logical_key=interrupted_turn.logical_key,
        )
    )
    replay = service.historical_turn_upsert(
        HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=stored_turn)
    )

    assert claim.outcome == "acquired"
    assert status.status == "committed"
    assert status.wire_sha256 == stored_turn.wire_sha256
    assert status.storage_row_key == stored.storage_row_key
    assert status.trace_ids == [stored_turn.trace_id]
    assert status.root_span_ids == [stored_turn.root_span_id]
    assert status.span_count == stored_turn.span_count
    assert replay.status == "replayed"
    assert (
        writer.row_count(
            project_id=PROJECT_ID,
            logical_key=stored_turn.logical_key,
        )
        == 1
    )


def test_storage_cas_prevents_duplicate_when_lease_expires_mid_commit(
    tmp_path, monkeypatch
) -> None:
    now_ns = [1_000_000_000]
    monkeypatch.setattr(
        "weave.trace_server.historical_turns.time.time_ns", lambda: now_ns[0]
    )
    database_path = tmp_path / "turns.db"
    store = SQLiteHistoricalTurnCommitStore(database_path)
    real_writer = SQLiteHistoricalTurnWriter(database_path)
    blocking_writer = BlockingCASWriter(real_writer)
    first_service, _, _ = _service(tmp_path, store=store, writer=blocking_writer)
    second_service, _, _ = _service(tmp_path, store=store, writer=blocking_writer)
    turn = _prepared_turn()
    request = HistoricalTurnUpsertReq(project_id=PROJECT_ID, turn=turn)

    with ThreadPoolExecutor(max_workers=1) as executor:
        first_future = executor.submit(first_service.historical_turn_upsert, request)
        assert blocking_writer.first_row_visible.wait(timeout=5)
        now_ns[0] += 2_000_000_000
        second = second_service.historical_turn_upsert(request)
        blocking_writer.release_first_caller.set()
        with pytest.raises(HistoricalTurnCommitError, match="lease"):
            first_future.result(timeout=5)

    status = second_service.historical_turn_status(
        HistoricalTurnStatusReq(project_id=PROJECT_ID, logical_key=turn.logical_key)
    )
    assert second.status == "committed"
    assert second.storage_row_key is not None
    assert status.status == "committed"
    assert status.storage_row_key == second.storage_row_key
    assert status.trace_ids == [turn.trace_id]
    assert status.root_span_ids == [turn.root_span_id]
    assert (
        real_writer.row_count(project_id=PROJECT_ID, logical_key=turn.logical_key) == 1
    )
    assert real_writer.read(project_id=PROJECT_ID, logical_key=turn.logical_key) == turn


def test_capabilities_and_sqlite_file_permissions(tmp_path) -> None:
    service, store, writer = _service(tmp_path)
    capabilities = service.historical_turn_capabilities(
        HistoricalTurnCapabilitiesReq(project_id=PROJECT_ID)
    )

    assert capabilities.model_dump() == {
        "supported": True,
        "capability_version": "historical-turn-v1",
        "transport_encoding": "canonical-json",
        "content_encoding": "identity",
        "preview_compression": "gzip-mtime-0",
        "schema_versions": ["1"],
        "max_envelope_bytes": 16 * 1024 * 1024,
        "max_spans": 512,
        "max_logical_key_bytes": 64,
        "atomic_turn_commit": True,
        "durable_idempotency": True,
        "status_lookup": True,
        "content_refs": "unsupported",
        "recovery_lease_seconds": 1,
        "reason": "",
    }
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(writer.path.stat().st_mode) == 0o600
    conn = sqlite3.connect(store.path)
    try:
        journal_columns = [
            str(row[1])
            for row in conn.execute("PRAGMA table_info(historical_turn_commits)")
        ]
    finally:
        conn.close()
    assert journal_columns == [
        "project_id",
        "logical_key",
        "wire_sha256",
        "status",
        "commit_id",
        "storage_row_key",
        "trace_ids_json",
        "root_span_ids_json",
        "span_count",
        "last_error",
        "lease_token",
        "lease_expires_ns",
        "created_at_ns",
        "updated_at_ns",
    ]
