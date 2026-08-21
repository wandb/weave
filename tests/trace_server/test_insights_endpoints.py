"""End-to-end tests for the insights endpoints against real ClickHouse.

Every test drives the endpoints only: it writes through `insights_signatures_write`
and reads through `insights_signatures_query`, never touching the tables directly,
so the SQL and the row hydration are both under test.
"""

import datetime
from typing import Literal

import pytest
from pydantic import ValidationError

from tests.trace_server.helpers import force_optimize, make_project_id
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.insights import config, writer
from weave.trace_server.insights.read_types import (
    InsightSignatureCursor,
    InsightSignaturesQueryReq,
    InsightSignaturesQueryRes,
)
from weave.trace_server.insights.write_types import (
    FailureSignatureCandidate,
    InsightSignaturesWriteReq,
    InsightSignaturesWriteRes,
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
    return config.deployed_config_sha(signature_type)


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


def _failure(
    turn: int, signature: str, **overrides: object
) -> FailureSignatureCandidate:
    fields: dict[str, object] = {
        "signature": signature,
        "category": "other",
        "conversation_id": CONVERSATION,
        "current_trace_id": TRACES[turn],
        "affected_trace_ids": [TRACES[turn]],
        "trace_started_at": _at(turn),
        "extracted_at": _at(turn),
        "vector": _vector(),
        "turn_duration_ms": 100 * (turn + 1),
        "turn_cost_usd": 0.01 * (turn + 1),
    }
    fields.update(overrides)
    return FailureSignatureCandidate(**fields)


SignatureType = Literal["intent", "failure"]


def _write(
    server, project_id: str, signature_type: SignatureType, **kwargs
) -> InsightSignaturesWriteRes:
    return server.insights_signatures_write(
        InsightSignaturesWriteReq(
            project_id=project_id,
            signature_type=signature_type,
            config_sha=_digest(signature_type),
            **kwargs,
        )
    )


def _write_intents(server, project_id: str, **kwargs) -> InsightSignaturesWriteRes:
    return _write(server, project_id, "intent", **kwargs)


def _query(server, project_id: str, **kwargs) -> InsightSignaturesQueryRes:
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
    assert written.written == 3
    assert written.dropped == {}

    failure = _failure(
        1,
        "agent ignored the stated output path",
        # Deliberately unsorted and duplicated: the writer canonicalizes.
        affected_trace_ids=[TRACES[3], TRACES[1], TRACES[1]],
        evidence_span_ids=["span-b", "span-a"],
        vector=_vector(0.25),
        severity="major",
        failure_reason="the user named /tmp/out.json and the agent wrote ./out.json",
        user_id="user-1",
        turn_cost_usd=0.5,
    )
    assert _write(ch_server, project_id, "failure", failures=[failure]).written == 1

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
    assert turn_intents.rows[0].language == "und"

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

    # The signature itself is the cluster join key, so filtering on it is how a
    # clustering job fetches the occurrences behind one of its clusters.
    by_signature_text = _query(
        ch_server,
        project_id,
        signature_type="intent",
        signatures=["explain why the build fails"],
        limit=50,
    )
    assert len(by_signature_text.rows) == 2

    # Groups: the repeated signature collapses, and users stay distinct from
    # conversations rather than being equated.
    groups = _query(ch_server, project_id, signature_type="intent", mode="groups")
    by_signature = {group.keys["signature"]: group for group in groups.groups}
    assert by_signature["explain why the build fails"].occurrences == 2
    assert by_signature["explain why the build fails"].turns == 2
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


def test_turn_measures_count_a_turn_once_on_intents(ch_server):
    """One turn emits several signatures, so turn cost and duration collapse onto it.

    Aggregated per row instead, this group would report twice the money the turn
    actually cost.
    """
    project_id = make_project_id("insights_turn_measures")
    _write_intents(
        ch_server,
        project_id,
        intents=[
            _intent(0, "add stripe checkout to the storefront"),
            _intent(0, "explain why the build fails"),
        ],
    )

    [group] = _query(
        ch_server,
        project_id,
        signature_type="intent",
        mode="groups",
        group_by=["category"],
    ).groups
    assert group.keys == {"category": "action_request"}
    assert group.occurrences == 2
    assert group.turns == 1
    assert group.avg_turn_cost_usd == pytest.approx(0.01)
    assert group.p50_turn_duration_ms == pytest.approx(100)


def test_turn_measures_count_a_turn_once_on_failures(ch_server):
    """Failure measures key on the detection turn, not on the turns it implicates.

    Two failures sharing an implicated turn must not bill that turn twice, and two
    failures detected in one turn must not bill that turn twice either.
    """
    project_id = make_project_id("insights_failure_measures")
    both_turns = [TRACES[1], TRACES[3]]
    _write(
        ch_server,
        project_id,
        "failure",
        failures=[
            # Two failures detected in turn 1, each implicating turns 1 and 3.
            _failure(1, "dropped the output path", affected_trace_ids=both_turns),
            _failure(1, "retried without backoff", affected_trace_ids=both_turns),
            # A third detected in turn 3, implicating the same pair.
            _failure(3, "gave up after one attempt", affected_trace_ids=both_turns),
        ],
    )

    [group] = _query(
        ch_server,
        project_id,
        signature_type="failure",
        mode="groups",
        group_by=["category"],
    ).groups
    assert group.occurrences == 3
    # Turns 1 and 3 are the two detection turns; turn 3 being implicated by the
    # first two failures does not make it a third.
    assert group.turns == 2
    # Turn 1 costs 0.02 and turn 3 costs 0.04, each counted once.
    assert group.avg_turn_cost_usd == pytest.approx(0.03)


def test_a_replay_reuses_the_row_id_so_the_merge_collapses_it(ch_server):
    """`id` is derived from the occurrence, so a retried write is not a new row.

    Before the merge both copies are visible; after it the later `inserted_at`
    wins. Without a derived id a retried batch would double every occurrence
    permanently, with no key to repair it on.
    """
    project_id = make_project_id("insights_replay")

    first = _write_intents(
        ch_server, project_id, intents=[_intent(1, "explain why the build fails")]
    )
    replay = _write_intents(
        ch_server,
        project_id,
        intents=[_intent(1, "explain why the build fails", sentiment="neutral")],
    )
    assert (first.written, replay.written) == (1, 1)

    before_merge = _query(
        ch_server, project_id, signature_type="intent", trace_id=TRACES[1]
    ).rows
    assert len({row.id for row in before_merge}) == 1

    force_optimize(ch_server.ch_client, "intent_signatures")
    after_merge = _query(
        ch_server, project_id, signature_type="intent", trace_id=TRACES[1]
    ).rows
    assert [row.sentiment for row in after_merge] == ["neutral"]

    # A different signature off the same turn is a different occurrence, so it
    # appends rather than replacing.
    _write_intents(ch_server, project_id, intents=[_intent(1, "a second intent")])
    force_optimize(ch_server.ch_client, "intent_signatures")
    both = _query(
        ch_server, project_id, signature_type="intent", trace_id=TRACES[1]
    ).rows
    assert sorted(row.signature for row in both) == [
        "a second intent",
        "explain why the build fails",
    ]


def test_writer_gates_repair_or_drop_and_count(ch_server):
    """Each bad candidate is counted without failing the batch."""
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
        "empty_signature": 1,
        "vector_dimensions": 1,
        "unknown_category": 1,
        "unknown_sentiment": 1,
        "duplicate_in_batch": 1,
    }
    assert result.written == 3

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

    ungrounded = _write(
        ch_server,
        project_id,
        "failure",
        failures=[
            _failure(
                0,
                "the current turn is not among the attributed turns",
                affected_trace_ids=[TRACES[2]],
            )
        ],
    )
    assert ungrounded.written == 0
    assert ungrounded.dropped == {"ungrounded_attribution": 1}


@pytest.mark.parametrize("signature_type", ["intent", "failure"])
def test_an_empty_batch_is_a_no_op(ch_server, signature_type: SignatureType):
    """A worker whose candidates were all filtered upstream needs no special case."""
    result = _write(ch_server, make_project_id("insights_empty"), signature_type)
    assert result.written == 0
    assert result.dropped == {}


def test_canonicalization_groups_phrasings_of_one_intent(ch_server):
    """Case, whitespace, and trailing periods are phrasing, not identity."""
    project_id = make_project_id("insights_canonical")
    _write_intents(
        ch_server,
        project_id,
        intents=[
            _intent(0, "Cancel My Subscription."),
            _intent(1, "  cancel   my subscription . . "),
            _intent(3, "cancel my subscription"),
        ],
    )

    [group] = _query(
        ch_server, project_id, signature_type="intent", mode="groups"
    ).groups
    assert group.keys == {"signature": "cancel my subscription"}
    assert group.occurrences == 3


def test_cursor_pagination_walks_every_row_exactly_once(ch_server):
    """The keyset cursor is a total order over the page set: no gaps, no repeats."""
    project_id = make_project_id("insights_cursor")
    total = 25
    page_size = 4

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
    assert _write_intents(ch_server, project_id, intents=intents).written == total

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
                limit=page_size,
            )
        )
        assert all(len(row.vector) == DIMENSIONS for row in page.rows)
        seen.extend((row.trace_started_at.date(), str(row.id)) for row in page.rows)
        cursor = page.next_cursor
        # A short page ends the walk, so the caller never spends a request to
        # discover the walk is over.
        if cursor is None:
            assert len(page.rows) < page_size
            break

    assert len(seen) == total
    assert len(set(seen)) == total
    # Days never go backwards, so the seek crosses the boundary without
    # re-opening a day it already finished. Ordering within a day is ClickHouse's
    # own UUID collation, which is not the text order and so is not asserted here.
    days = [day for day, _ in seen]
    assert days == sorted(days)


def test_write_rejects_a_config_the_server_cannot_resolve(ch_server):
    with pytest.raises(InvalidRequest, match="does not match the deployed config"):
        ch_server.insights_signatures_write(
            InsightSignaturesWriteReq(
                project_id=make_project_id("insights_config"),
                signature_type="intent",
                config_sha="0" * 64,
                intents=[_intent(0, "a signature")],
            )
        )


def test_a_write_carries_only_the_signature_type_it_names():
    with pytest.raises(ValidationError, match="so failures must be empty"):
        InsightSignaturesWriteReq(
            project_id="p",
            signature_type="intent",
            config_sha="0" * 64,
            intents=[_intent(0, "one signature type per call")],
            failures=[_failure(0, "two signature types in one call")],
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        pytest.param(
            {"day_start": datetime.date(2026, 6, 2), "day_end": DAY},
            "is after day_end",
            id="a_reversed_window_is_not_an_empty_one",
        ),
        pytest.param(
            {"mode": "groups", "include_vector": True},
            "does not read include_vector",
            id="groups_does_not_read_a_rows_knob",
        ),
        pytest.param(
            {"mode": "groups", "order": "key", "cursor": None},
            "does not read cursor, order",
            id="groups_does_not_read_order_or_cursor",
        ),
        pytest.param(
            {"group_by": ["category"]},
            "does not read group_by",
            id="rows_does_not_read_a_groups_knob",
        ),
        pytest.param(
            {"cursor": InsightSignatureCursor(day=DAY, id="0" * 32)},
            "cursor requires order='key'",
            id="a_cursor_without_key_order_would_be_ignored",
        ),
        pytest.param(
            {"include_vector": True, "order": "key", "limit": 5000},
            "include_vector caps limit",
            id="a_vector_page_has_a_lower_ceiling",
        ),
        pytest.param(
            {"limit": 10_001}, "less than or equal to 10000", id="limit_has_a_ceiling"
        ),
        pytest.param(
            {"limit": 0}, "greater than or equal to 1", id="limit_has_a_floor"
        ),
        pytest.param(
            {"mode": "groups", "group_by": []},
            "at least one field",
            id="groups_needs_a_key",
        ),
    ],
)
def test_incoherent_queries_are_rejected(overrides: dict, message: str):
    """A knob the chosen mode cannot read is an error, never a silent no-op."""
    fields: dict[str, object] = {
        "project_id": "p",
        "signature_type": "intent",
        "day_start": DAY,
        "day_end": DAY,
    }
    fields.update(overrides)
    with pytest.raises(ValidationError, match=message):
        InsightSignaturesQueryReq(**fields)
