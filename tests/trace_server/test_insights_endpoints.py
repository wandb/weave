"""End-to-end tests for the insights endpoints against real ClickHouse.

Every test drives the endpoints only: it writes through `insights_signatures_write`
and reads through `insights_signatures_query`, never touching the tables directly,
so the SQL and the row hydration are both under test.
"""

import datetime

import pytest

from tests.trace_server.helpers import force_optimize, make_project_id
from weave.trace_server.insights import config, writer
from weave.trace_server.insights.types import (
    FailureSignatureCandidate,
    InsightSignaturesQueryReq,
    InsightSignaturesWriteReq,
    IntentSignatureCandidate,
)

DAY = datetime.date(2026, 6, 1)
DIMENSIONS = 1024
CONVERSATION = "conv-1"
TRACES = ["trace-0", "trace-1", "trace-2", "trace-3"]


def _at(turn: int) -> datetime.datetime:
    return datetime.datetime(2026, 6, 1, 12, turn, tzinfo=datetime.timezone.utc)


def _vector(seed: float = 0.5) -> list[float]:
    return [seed] * DIMENSIONS


def _digest(signature_type: str) -> str:
    return config.config_sha(config.load_config(signature_type))


def _intent(turn: int, signature: str, **overrides: object) -> IntentSignatureCandidate:
    fields: dict[str, object] = {
        "signature": signature,
        "category": "action_request",
        "conversation_id": CONVERSATION,
        "trace_id": TRACES[turn],
        "trace_started_at": _at(turn),
        "extracted_at": _at(turn),
        "vector": _vector(),
        "sentiment": "frustrated",
        "user_id": f"user-{turn % 2}",
        "turn_duration_ms": 100 * (turn + 1),
        "turn_cost_usd": 0.01 * (turn + 1),
    }
    fields.update(overrides)
    return IntentSignatureCandidate(**fields)


def _write_intents(server, project_id: str, **kwargs) -> object:
    return server.insights_signatures_write(
        InsightSignaturesWriteReq(
            project_id=project_id, config_sha=_digest("intent"), **kwargs
        )
    )


def _query(server, project_id: str, **kwargs) -> object:
    return server.insights_signatures_query(
        InsightSignaturesQueryReq(
            project_id=project_id,
            day_start=DAY,
            day_end=DAY,
            **kwargs,
        )
    )


def test_write_read_and_project_isolation(ch_server):
    """The whole Tier 1 loop: write both signature types, read every shape, isolate."""
    project_id = make_project_id("insights")
    other_project = make_project_id("insights_other")

    # Turn 3 repeats turn 1's signature, so grouping has something to collapse.
    intents = [
        _intent(0, "add stripe checkout to the storefront"),
        _intent(1, "explain why the build fails"),
        _intent(3, "explain why the build fails", user_id="user-9"),
    ]
    written = _write_intents(ch_server, project_id, intents=intents)
    assert written.written.intents == 3
    assert written.dropped == {}

    failure = FailureSignatureCandidate(
        signature="agent ignored the stated output path",
        category="other",
        conversation_id=CONVERSATION,
        current_trace_id=TRACES[1],
        # Deliberately unsorted and duplicated: the writer canonicalizes.
        affected_trace_ids=[TRACES[3], TRACES[1], TRACES[1]],
        evidence_span_ids=["span-b", "span-a"],
        trace_started_at=_at(1),
        extracted_at=_at(1),
        vector=_vector(0.25),
        severity="major",
        failure_reason="the user named /tmp/out.json and the agent wrote ./out.json",
        user_id="user-1",
        turn_cost_usd=0.5,
    )
    failure_write = ch_server.insights_signatures_write(
        InsightSignaturesWriteReq(
            project_id=project_id,
            config_sha=_digest("failure"),
            failures=[failure],
        )
    )
    assert failure_write.written.failures == 1

    # A second project holding the same signatures must never surface below.
    _write_intents(
        ch_server,
        other_project,
        intents=[_intent(0, "add stripe checkout to the storefront")],
    )

    # Turn drilldown, intent: equality on trace_id.
    turn_intents = _query(
        ch_server, project_id, signature_type="intent", trace_id=TRACES[1]
    )
    assert [row.signature for row in turn_intents.rows] == [
        "explain why the build fails"
    ]
    assert turn_intents.rows[0].sentiment == "frustrated"
    assert turn_intents.cost_is_additive is True

    # Turn drilldown, failure: has() over affected_trace_ids, on a turn that is
    # attributed but is not the turn the failure was detected in.
    turn_failures = _query(
        ch_server, project_id, signature_type="failure", trace_id=TRACES[3]
    )
    assert [row.signature for row in turn_failures.rows] == [
        "agent ignored the stated output path"
    ]
    assert turn_failures.rows[0].affected_trace_ids == [TRACES[1], TRACES[3]]
    assert turn_failures.rows[0].evidence_span_ids == ["span-a", "span-b"]
    assert turn_failures.rows[0].severity == "major"
    assert turn_failures.cost_is_additive is False

    # Groups: the repeated signature collapses, and users stay distinct from
    # conversations rather than being equated.
    groups = _query(ch_server, project_id, signature_type="intent", mode="groups")
    by_signature = {group.keys["signature"]: group for group in groups.groups}
    assert by_signature["explain why the build fails"].occurrences == 2
    assert by_signature["explain why the build fails"].users == 2
    assert by_signature["explain why the build fails"].conversations == 1
    assert by_signature["explain why the build fails"].configs == [_digest("intent")]
    assert by_signature["add stripe checkout to the storefront"].occurrences == 1

    # Project isolation on every read.
    assert (
        _query(
            ch_server, other_project, signature_type="intent", trace_id=TRACES[1]
        ).rows
        == []
    )
    assert _query(ch_server, other_project, signature_type="failure").rows == []


def test_a_re_extraction_appends_rather_than_replacing(ch_server):
    """The tables mint `id`, so nothing a caller sends can replace a stored row.

    A merge must not collapse the two either: they differ in `id`, which is in
    the sorting key, so the ReplacingMergeTree has nothing to replace.
    """
    project_id = make_project_id("insights_reextract")

    _write_intents(
        ch_server, project_id, intents=[_intent(1, "explain why the build fails")]
    )
    _write_intents(
        ch_server,
        project_id,
        intents=[_intent(1, "explain why the build fails", sentiment="neutral")],
    )

    rows = _query(
        ch_server, project_id, signature_type="intent", trace_id=TRACES[1]
    ).rows
    assert sorted(row.sentiment for row in rows) == ["frustrated", "neutral"]
    assert len({row.id for row in rows}) == 2

    force_optimize(ch_server.ch_client, "intent_signatures")
    after_merge = _query(
        ch_server, project_id, signature_type="intent", trace_id=TRACES[1]
    ).rows
    assert sorted(row.sentiment for row in after_merge) == ["frustrated", "neutral"]


def test_writer_gates_drop_candidates_and_count_them(ch_server):
    """One bad candidate per gate never fails the batch, and each is counted."""
    project_id = make_project_id("insights_gates")

    result = _write_intents(
        ch_server,
        project_id,
        intents=[
            _intent(0, "a genuinely useful signature"),
            _intent(1, "   "),
            _intent(2, "wrong width", vector=[0.1] * 8),
            _intent(3, "unknown label", category="not_a_category"),
            _intent(0, "unknown mood", sentiment="euphoric"),
            # Same turn and signature as the first, so one occurrence, not two.
            _intent(0, "a genuinely useful signature"),
        ],
    )
    assert result.dropped == {
        writer.GATE_EMPTY_SIGNATURE: 1,
        writer.GATE_VECTOR_DIMENSIONS: 1,
        writer.GATE_UNKNOWN_CATEGORY: 1,
        writer.GATE_UNKNOWN_SENTIMENT: 1,
        writer.GATE_DUPLICATE_IN_BATCH: 1,
    }
    assert result.written.intents == 3

    rows = _query(ch_server, project_id, signature_type="intent", limit=50).rows
    assert sorted(row.signature for row in rows) == [
        "a genuinely useful signature",
        "unknown label",
        "unknown mood",
    ]
    labels = {row.signature: (row.category, row.sentiment) for row in rows}
    assert labels["unknown label"] == (writer.FALLBACK_LABEL, "frustrated")
    # An unusable sentiment is '' rather than the real `neutral` label.
    assert labels["unknown mood"] == ("action_request", "")

    ungrounded = ch_server.insights_signatures_write(
        InsightSignaturesWriteReq(
            project_id=project_id,
            config_sha=_digest("failure"),
            failures=[
                FailureSignatureCandidate(
                    signature="the current turn is not among the attributed turns",
                    category="other",
                    conversation_id=CONVERSATION,
                    current_trace_id=TRACES[0],
                    affected_trace_ids=[TRACES[2]],
                    trace_started_at=_at(0),
                    extracted_at=_at(0),
                    vector=_vector(),
                )
            ],
        )
    )
    assert ungrounded.written.failures == 0
    assert ungrounded.dropped == {writer.GATE_UNGROUNDED_ATTRIBUTION: 1}


def test_cursor_pagination_walks_every_row_exactly_once(ch_server):
    """The keyset cursor is a total order over the page set: no gaps, no repeats."""
    project_id = make_project_id("insights_cursor")
    total = 25

    # Spread across two days so the cursor has to cross a day boundary, which is
    # the case the spelled-out OR predicate exists to handle.
    intents = [
        _intent(
            index % 4,
            f"signature number {index}",
            trace_started_at=datetime.datetime(
                2026, 6, 1 + index % 2, 12, index, tzinfo=datetime.timezone.utc
            ),
        )
        for index in range(total)
    ]
    written = _write_intents(ch_server, project_id, intents=intents)
    assert written.written.intents == total

    seen: list[tuple[datetime.date, str]] = []
    cursor = None
    for _ in range(total):
        page = ch_server.insights_signatures_query(
            InsightSignaturesQueryReq(
                project_id=project_id,
                signature_type="intent",
                day_start=datetime.date(2026, 6, 1),
                day_end=datetime.date(2026, 6, 2),
                order="key",
                cursor=cursor,
                include_vector=True,
                limit=4,
            )
        )
        if not page.rows:
            break
        assert all(len(row.vector) == DIMENSIONS for row in page.rows)
        seen.extend((row.trace_started_at.date(), str(row.id)) for row in page.rows)
        cursor = page.next_cursor

    assert len(seen) == total
    assert len(set(seen)) == total
    # Days never go backwards, so the seek crosses the boundary without
    # re-opening a day it already finished. Ordering within a day is ClickHouse's
    # own UUID collation, which is not the text order and so is not asserted here.
    days = [day for day, _ in seen]
    assert days == sorted(days)


def test_write_rejects_a_config_the_server_cannot_resolve(ch_server):
    project_id = make_project_id("insights_config")

    with pytest.raises(writer.InsightWriteRejected):
        ch_server.insights_signatures_write(
            InsightSignaturesWriteReq(
                project_id=project_id,
                config_sha="0" * 64,
                intents=[_intent(0, "a signature")],
            )
        )

    with pytest.raises(writer.InsightWriteRejected):
        ch_server.insights_signatures_write(
            InsightSignaturesWriteReq(
                project_id=project_id,
                config_sha=_digest("intent"),
                intents=[_intent(0, "one signature type per call")],
                failures=[
                    FailureSignatureCandidate(
                        signature="two signature types in one call",
                        category="other",
                        conversation_id=CONVERSATION,
                        current_trace_id=TRACES[0],
                        affected_trace_ids=[TRACES[0]],
                        trace_started_at=_at(0),
                        extracted_at=_at(0),
                        vector=_vector(),
                    )
                ],
            )
        )
