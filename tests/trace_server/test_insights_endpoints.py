"""End-to-end tests for the insights endpoints against real ClickHouse.

Every test drives the endpoints only: it writes through `insights_signatures_write`
and reads through `insights_context_query` / `insights_signatures_query`, never
touching the tables directly, so the SQL and the row hydration are both under test.
"""

import datetime
import uuid

import pytest

from tests.trace_server.helpers import force_optimize, make_project_id
from weave.trace_server.insights import config, writer
from weave.trace_server.insights.types import (
    FailureSignatureCandidate,
    InsightContextQueryReq,
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


def _digest(space: str) -> str:
    return config.config_sha(config.load_config(space))


def _intent(turn: int, signature: str, **overrides: object) -> IntentSignatureCandidate:
    fields: dict[str, object] = {
        "signature": signature,
        "category": "action_request",
        "conversation_id": CONVERSATION,
        "turn_trace_id": TRACES[turn],
        "source_started_at": _at(turn),
        "extracted_at": _at(turn),
        "vector": _vector(),
        "sentiment": "frustrated",
        "user_id": f"user-{turn % 2}",
        "duration_ms": 100 * (turn + 1),
        "cost_usd": 0.01 * (turn + 1),
    }
    fields.update(overrides)
    return IntentSignatureCandidate(**fields)


def _failure(
    onset: int, signature: str, turns: list[str], **overrides: object
) -> FailureSignatureCandidate:
    fields: dict[str, object] = {
        "signature": signature,
        "category": "other",
        "conversation_id": CONVERSATION,
        "onset_turn_trace_id": TRACES[onset],
        "turn_trace_ids": turns,
        "source_started_at": _at(onset),
        "extracted_at": _at(onset),
        "vector": _vector(0.25),
    }
    fields.update(overrides)
    return FailureSignatureCandidate(**fields)


def _write_intents(server, project_id: str, **kwargs) -> object:
    return server.insights_signatures_write(
        InsightSignaturesWriteReq(
            project_id=project_id, config_sha=_digest("intent"), **kwargs
        )
    )


def _write_failures(server, project_id: str, **kwargs) -> object:
    return server.insights_signatures_write(
        InsightSignaturesWriteReq(
            project_id=project_id, config_sha=_digest("failure"), **kwargs
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


def _context(server, project_id: str, turns: list[str]) -> object:
    return server.insights_context_query(
        InsightContextQueryReq(
            project_id=project_id,
            conversation_id=CONVERSATION,
            turn_trace_ids=turns,
            day_start=DAY,
            day_end=DAY,
        )
    )


def test_write_read_replace_and_project_isolation(ch_server):
    """The whole Tier 1 loop: write both lenses, read every shape, replace, isolate."""
    project_id = make_project_id("insights")
    other_project = make_project_id("insights_other")

    # Turn 3 repeats turn 1's signature so grouping has something to collapse.
    # Turn 2 produces nothing at all, which is why the context endpoint cannot
    # enumerate a conversation's turns and takes them from the caller instead.
    intents = [
        _intent(0, "Add Stripe checkout to the storefront."),
        _intent(1, "explain why the build fails"),
        _intent(3, "explain why the build fails", user_id="user-9"),
    ]
    written = _write_intents(ch_server, project_id, intents=intents)
    assert written.written.intents == 3
    assert written.dropped == {}

    failure_write = _write_failures(
        ch_server,
        project_id,
        failures=[
            _failure(
                1,
                "agent ignored the stated output path",
                # Deliberately unsorted and duplicated: the writer canonicalizes.
                [TRACES[3], TRACES[1], TRACES[1]],
                severity="major",
                failure_reason="the user named /tmp/out.json and the agent wrote ./out.json",
                evidence_span_ids=["span-a", "span-b"],
                user_id="user-1",
                cost_usd=0.5,
            )
        ],
    )
    assert failure_write.written.failures == 1

    # A second project holding the same signatures must never surface below.
    _write_intents(
        ch_server,
        other_project,
        intents=[_intent(0, "Add Stripe checkout to the storefront.")],
    )

    # Context: both lenses for the turns the caller names, and a failure spanning
    # two turns is context for each of them.
    context = _context(ch_server, project_id, TRACES)
    by_turn: dict[str, list[str]] = {}
    for signature in context.signatures:
        by_turn.setdefault(signature.turn_trace_id, []).append(signature.lens)
    assert by_turn[TRACES[0]] == ["intent"]
    assert sorted(by_turn[TRACES[1]]) == ["failure", "intent"]
    assert TRACES[2] not in by_turn
    assert sorted(by_turn[TRACES[3]]) == ["failure", "intent"]
    # Canonical for identity, the judge's own wording for display.
    stripe = next(s for s in context.signatures if s.turn_trace_id == TRACES[0])
    assert stripe.signature == "add stripe checkout to the storefront"
    assert stripe.signature_display == "Add Stripe checkout to the storefront."
    assert stripe.config_sha == _digest("intent")

    # A turn subset returns only that subset, and the unnest never leaks the
    # sibling turns of a failure nobody asked about.
    bounded = _context(ch_server, project_id, [TRACES[3]])
    assert {s.turn_trace_id for s in bounded.signatures} == {TRACES[3]}
    assert sorted(s.lens for s in bounded.signatures) == ["failure", "intent"]
    assert _context(ch_server, project_id, []).signatures == []

    # Turn drilldown, intent lens: equality on turn_trace_id.
    turn_intents = _query(ch_server, project_id, lens="intent", turn_trace_id=TRACES[1])
    assert [row.signature for row in turn_intents.rows] == [
        "explain why the build fails"
    ]
    assert turn_intents.rows[0].sentiment == "frustrated"
    assert turn_intents.rows[0].language == "und"
    assert uuid.UUID(turn_intents.rows[0].id)
    assert turn_intents.cost_is_additive is True

    # Turn drilldown, failure lens: has() over turn_trace_ids, on a non-onset turn.
    turn_failures = _query(
        ch_server, project_id, lens="failure", turn_trace_id=TRACES[3]
    )
    assert [row.signature for row in turn_failures.rows] == [
        "agent ignored the stated output path"
    ]
    assert turn_failures.rows[0].turn_trace_ids == [TRACES[1], TRACES[3]]
    assert turn_failures.rows[0].evidence_span_ids == ["span-a", "span-b"]
    assert turn_failures.rows[0].severity == "major"
    assert turn_failures.cost_is_additive is False

    # Groups: the repeated signature collapses, and users stay distinct from
    # conversations rather than being equated.
    groups = _query(ch_server, project_id, lens="intent", mode="groups")
    by_signature = {group.keys["signature"]: group for group in groups.groups}
    assert by_signature["explain why the build fails"].occurrences == 2
    assert by_signature["explain why the build fails"].users == 2
    assert by_signature["explain why the build fails"].conversations == 1
    assert by_signature["explain why the build fails"].configs == [_digest("intent")]
    assert by_signature["add stripe checkout to the storefront"].occurrences == 1

    # Re-extraction replaces rather than duplicating, and the read reflects the
    # new value before any merge has run.
    _write_intents(
        ch_server,
        project_id,
        intents=[_intent(1, "explain why the build fails", sentiment="neutral")],
    )
    reread = _query(ch_server, project_id, lens="intent", turn_trace_id=TRACES[1])
    assert [row.sentiment for row in reread.rows] == ["neutral"]

    force_optimize(ch_server.ch_client, "intent_signatures")
    after_merge = _query(ch_server, project_id, lens="intent", turn_trace_id=TRACES[1])
    assert [row.sentiment for row in after_merge.rows] == ["neutral"]
    assert after_merge.rows[0].id == reread.rows[0].id

    # Project isolation on every read.
    assert (
        _query(ch_server, other_project, lens="intent", turn_trace_id=TRACES[1]).rows
        == []
    )
    assert _query(ch_server, other_project, lens="failure").rows == []
    assert _context(ch_server, other_project, [TRACES[1]]).signatures == []


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
            # Same turn and signature as the first: one id, so one row.
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

    rows = _query(ch_server, project_id, lens="intent", limit=50).rows
    assert sorted(row.signature for row in rows) == [
        "a genuinely useful signature",
        "unknown label",
        "unknown mood",
    ]
    labels = {row.signature: (row.category, row.sentiment) for row in rows}
    assert labels["unknown label"] == (writer.FALLBACK_LABEL, "frustrated")
    assert labels["unknown mood"] == ("action_request", "")

    ungrounded = _write_failures(
        ch_server,
        project_id,
        failures=[
            _failure(0, "onset is not among the attributed turns", [TRACES[2]]),
        ],
    )
    assert ungrounded.written.failures == 0
    assert ungrounded.dropped == {writer.GATE_UNGROUNDED_ATTRIBUTION: 1}

    # Evidence over the config's `max_evidence_spans` is truncated, not dropped:
    # the failure is still real and the config owns the bound.
    cap = writer.failure_config().extraction.max_evidence_spans
    truncated = _write_failures(
        ch_server,
        project_id,
        failures=[
            _failure(
                0,
                "cited more evidence than the config allows",
                [TRACES[0]],
                evidence_span_ids=[f"span-{i}" for i in range(cap + 2)],
            )
        ],
    )
    assert truncated.written.failures == 1
    assert truncated.dropped == {}
    stored = _query(ch_server, project_id, lens="failure", turn_trace_id=TRACES[0]).rows
    assert stored[0].evidence_span_ids == [f"span-{i}" for i in range(cap)]


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
            source_started_at=datetime.datetime(
                2026, 6, 1 + index % 2, 12, index, tzinfo=datetime.timezone.utc
            ),
        )
        for index in range(total)
    ]
    written = _write_intents(ch_server, project_id, intents=intents)
    assert written.written.intents == total

    def _page(cursor: object, limit: int) -> object:
        return ch_server.insights_signatures_query(
            InsightSignaturesQueryReq(
                project_id=project_id,
                lens="intent",
                day_start=datetime.date(2026, 6, 1),
                day_end=datetime.date(2026, 6, 2),
                order="key",
                cursor=cursor,
                include_vector=True,
                limit=limit,
            )
        )

    seen: list[tuple[datetime.date, str]] = []
    cursor = None
    for _ in range(total):
        page = _page(cursor, 4)
        if not page.rows:
            break
        assert all(len(row.vector) == DIMENSIONS for row in page.rows)
        seen.extend((row.source_started_at.date(), row.id) for row in page.rows)
        cursor = page.next_cursor

    assert len(seen) == total
    assert len(set(seen)) == total
    # The paged walk reproduces the table's own order exactly, which is the real
    # guarantee: `id` is a UUID, and ClickHouse compares a UUID by its low 64 bits
    # first, so the sequence is a total order in ClickHouse's terms and not in
    # lexicographic ones. Asserting against one unpaged read keeps this test from
    # smuggling in a client-side ordering the server never promised.
    unpaged = _page(None, total)
    assert seen == [(row.source_started_at.date(), row.id) for row in unpaged.rows]
    # Cursors are therefore opaque to the client: parse it, never compare it.
    assert uuid.UUID(seen[0][1])


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
                intents=[_intent(0, "one space per call")],
                failures=[_failure(0, "two spaces in one call", [TRACES[0]])],
            )
        )
