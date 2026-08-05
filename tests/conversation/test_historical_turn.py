from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Literal

import pytest

from weave.conversation import historical_turn
from weave.conversation.conversation import LLM, Tool
from weave.conversation.types import Message
from weave.trace_server.agents import historical_turn_validation
from weave.trace_server.agents.historical_turn_validation import (
    HistoricalTurnPayloadTooLargeError,
    HistoricalTurnValidationError,
    compute_historical_turn_logical_key,
    compute_historical_turn_root_span_id,
    compute_historical_turn_trace_id,
)
from weave.trace_server.agents.types import (
    HistoricalTurnStatusRes,
    HistoricalTurnUpsertRes,
    PreparedTurn,
)

PROJECT_ID = "wandb/hivemind-chats"


def _install_project(monkeypatch, project_id: str = PROJECT_ID) -> None:
    monkeypatch.setattr(
        historical_turn,
        "require_weave_client",
        lambda: SimpleNamespace(project_id=project_id),
    )


def _prepare(monkeypatch, *, message: str = "hello"):
    _install_project(monkeypatch)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    llm = LLM(
        model="gpt-5",
        provider_name="openai",
        input_messages=[Message.user(message)],
        output_messages=[Message.assistant("done")],
        started_at=start,
        ended_at=end,
    )
    tool = Tool(
        name="shell",
        arguments={"cmd": "pwd"},
        result={"exit_code": 0},
        started_at=start,
        ended_at=end,
    )
    return historical_turn.prepare_turn(
        conversation_id="hivemind:session-42",
        turn_key="turn-7",
        source_payload_sha256=hashlib.sha256(message.encode()).hexdigest(),
        agent_name="codex",
        conversation_name="Importer work",
        messages=[Message.user(message)],
        output_messages=[Message.assistant("done")],
        spans=[llm, tool],
        started_at=start,
        ended_at=end,
        attributes={"hivemind.session_id": "session-42"},
    )


def test_prepare_is_deterministic_and_project_scoped(monkeypatch) -> None:
    first = _prepare(monkeypatch)
    second = _prepare(monkeypatch)

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.logical_key == compute_historical_turn_logical_key(
        PROJECT_ID, "hivemind:session-42", "turn-7"
    )
    assert len(first.logical_key) == 64
    assert first.destination_project_id == PROJECT_ID
    assert first.capability_version == "historical-turn-v1"
    assert first.compressed_bytes > 0
    assert first.uncompressed_bytes > 0
    assert first.reference_count == 0
    assert first.span_count == 3
    assert first.spans[0].parent_span_id is None
    assert [span.parent_span_id for span in first.spans[1:]] == [
        first.root_span_id,
        first.root_span_id,
    ]

    _install_project(monkeypatch, "wandb/other-project")
    other_project = historical_turn.prepare_turn(
        conversation_id="hivemind:session-42",
        turn_key="turn-7",
        source_payload_sha256=hashlib.sha256(b"hello").hexdigest(),
        agent_name="codex",
        messages=[Message.user("hello")],
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ended_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
    )
    assert other_project.logical_key != first.logical_key


def test_changed_content_keeps_key_and_changes_wire_hash(monkeypatch) -> None:
    first = _prepare(monkeypatch, message="first")
    changed = _prepare(monkeypatch, message="changed")

    assert changed.logical_key == first.logical_key
    assert changed.wire_sha256 != first.wire_sha256


def test_prepare_rejects_reserved_attributes(monkeypatch) -> None:
    _install_project(monkeypatch)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(
        HistoricalTurnValidationError,
        match="historical ingest attribute 'gen_ai.provider.name' uses a reserved namespace",
    ):
        historical_turn.prepare_turn(
            conversation_id="conversation",
            turn_key="turn",
            source_payload_sha256="0" * 64,
            started_at=now,
            ended_at=now,
            attributes={"gen_ai.provider.name": "spoofed"},
        )


def test_prepare_rejects_missing_historical_timestamp(monkeypatch) -> None:
    _install_project(monkeypatch)

    with pytest.raises(
        HistoricalTurnValidationError,
        match="started_at is required for historical ingest",
    ):
        historical_turn.prepare_turn(
            conversation_id="conversation",
            turn_key="turn",
            source_payload_sha256="0" * 64,
            ended_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


def test_prepare_rejects_oversize_without_truncating(monkeypatch) -> None:
    _install_project(monkeypatch)
    monkeypatch.setattr(
        historical_turn_validation,
        "MAX_HISTORICAL_TURN_ENVELOPE_BYTES",
        1_000,
    )
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(
        HistoricalTurnPayloadTooLargeError,
        match=(
            r"historical turn is [0-9]+ bytes; maximum is 1000\. This server "
            r"does not yet support externalized historical-turn content; content "
            r"was not truncated\."
        ),
    ) as exc_info:
        historical_turn.prepare_turn(
            conversation_id="conversation",
            turn_key="turn",
            source_payload_sha256="0" * 64,
            messages=[Message.user("x" * 2_000)],
            started_at=now,
            ended_at=now,
        )

    assert exc_info.value.http_status_code == 413


def _install_status_response(monkeypatch, response: HistoricalTurnStatusRes) -> None:
    server = SimpleNamespace(historical_turn_status=lambda request: response)
    monkeypatch.setattr(
        historical_turn,
        "require_weave_client",
        lambda: SimpleNamespace(project_id=PROJECT_ID, server=server),
    )


def _committed_status(**updates) -> HistoricalTurnStatusRes:
    logical_key = "a" * 64
    return HistoricalTurnStatusRes(
        logical_key=logical_key,
        status="committed",
        wire_sha256="b" * 64,
        commit_id="commit-1",
        storage_row_key="row-1",
        trace_ids=[compute_historical_turn_trace_id(logical_key)],
        root_span_ids=[compute_historical_turn_root_span_id(logical_key)],
        span_count=3,
    ).model_copy(update=updates)


@pytest.mark.parametrize(
    "response",
    [
        HistoricalTurnStatusRes(logical_key="a" * 64, status="absent"),
        _committed_status(),
        _committed_status(status="committing", storage_row_key=None),
    ],
    ids=["absent", "committed", "committing"],
)
def test_get_turn_status_accepts_consistent_evidence(
    monkeypatch, response: HistoricalTurnStatusRes
) -> None:
    _install_status_response(monkeypatch, response)

    assert historical_turn.get_turn_status("a" * 64) == response


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            _committed_status(logical_key="f" * 64),
            "historical turn status returned a different logical_key",
        ),
        (
            HistoricalTurnStatusRes(
                logical_key="a" * 64,
                status="absent",
                wire_sha256="b" * 64,
            ),
            "absent historical turn status returned commit evidence",
        ),
        (
            _committed_status(wire_sha256="not-a-digest"),
            "historical turn status returned an invalid wire_sha256",
        ),
        (
            _committed_status(commit_id=""),
            "historical turn status returned an empty commit_id",
        ),
        (
            _committed_status(trace_ids=["not-a-trace-id"]),
            "historical turn status returned invalid trace_ids",
        ),
        (
            _committed_status(root_span_ids=[]),
            "historical turn status returned invalid root_span_ids",
        ),
        (
            _committed_status(span_count=0),
            "historical turn status returned an invalid span_count",
        ),
        (
            _committed_status(storage_row_key=None),
            "committed historical turn status returned an empty storage_row_key",
        ),
        (
            _committed_status(last_error="commit_attempt_failed"),
            "committed historical turn status returned a last_error",
        ),
        (
            _committed_status(status="committing"),
            "committing historical turn status returned a storage_row_key",
        ),
    ],
    ids=[
        "logical-key",
        "absent-evidence",
        "wire-digest",
        "commit-id",
        "trace-id",
        "root-span-id",
        "span-count",
        "committed-storage-row",
        "committed-last-error",
        "committing-storage-row",
    ],
)
def test_get_turn_status_rejects_inconsistent_evidence(
    monkeypatch,
    response: HistoricalTurnStatusRes,
    message: str,
) -> None:
    _install_status_response(monkeypatch, response)

    with pytest.raises(RuntimeError, match=f"^{message}$"):
        historical_turn.get_turn_status("a" * 64)


def _install_upsert_response(monkeypatch, response: HistoricalTurnUpsertRes) -> None:
    server = SimpleNamespace(historical_turn_upsert=lambda request: response)
    monkeypatch.setattr(
        historical_turn,
        "require_weave_client",
        lambda: SimpleNamespace(project_id=PROJECT_ID, server=server),
    )


def _upsert_response(
    prepared: PreparedTurn,
    status: Literal["committing", "committed", "replayed", "conflict"],
    **updates,
) -> HistoricalTurnUpsertRes:
    if status == "conflict":
        response = HistoricalTurnUpsertRes(
            logical_key=prepared.logical_key,
            wire_sha256=prepared.wire_sha256,
            status="conflict",
            storage_row_key="existing-row",
            existing_wire_sha256="f" * 64,
        )
    else:
        response = HistoricalTurnUpsertRes(
            logical_key=prepared.logical_key,
            wire_sha256=prepared.wire_sha256,
            status=status,
            commit_id="commit-1",
            storage_row_key=None if status == "committing" else "row-1",
            trace_ids=[prepared.trace_id],
            root_span_ids=[prepared.root_span_id],
            span_count=prepared.span_count,
        )
    return response.model_copy(update=updates)


@pytest.mark.parametrize(
    "status",
    ["committing", "committed", "replayed", "conflict"],
)
def test_upsert_turn_accepts_status_consistent_evidence(
    monkeypatch,
    status: Literal["committing", "committed", "replayed", "conflict"],
) -> None:
    prepared = _prepare(monkeypatch)
    response = _upsert_response(prepared, status)
    _install_upsert_response(monkeypatch, response)

    assert historical_turn.upsert_turn(prepared) == response


@pytest.mark.parametrize(
    ("status", "updates", "message"),
    [
        (
            "committed",
            {"commit_id": None},
            "historical turn server returned an empty commit_id",
        ),
        (
            "replayed",
            {"storage_row_key": None},
            "committed historical turn response returned an empty storage_row_key",
        ),
        (
            "committing",
            {"storage_row_key": "premature-row"},
            "committing historical turn response returned a storage_row_key",
        ),
        (
            "conflict",
            {"existing_wire_sha256": None},
            "historical turn conflict returned an invalid existing_wire_sha256",
        ),
        (
            "conflict",
            {"commit_id": "contradictory-commit"},
            "historical turn conflict returned contradictory commit evidence",
        ),
        (
            "committed",
            {"existing_wire_sha256": "f" * 64},
            "historical turn server returned an unexpected existing_wire_sha256",
        ),
    ],
)
def test_upsert_turn_rejects_status_inconsistent_evidence(
    monkeypatch,
    status: Literal["committing", "committed", "replayed", "conflict"],
    updates: dict,
    message: str,
) -> None:
    prepared = _prepare(monkeypatch)
    response = _upsert_response(prepared, status, **updates)
    _install_upsert_response(monkeypatch, response)

    with pytest.raises(RuntimeError, match=f"^{message}$"):
        historical_turn.upsert_turn(prepared)
