"""Integration tests for GenAI agent tables and query layer.

Runs against the ClickHouse backend (the only supported backend).
Migration 030 creates the genai tables automatically.
"""

import base64
import datetime
import json
import uuid

import pytest
from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

from tests.trace_server.helpers import make_project_id as _make_project_id
from weave.shared import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.clickhouse import AgentWriteHandler
from weave.trace_server.agents.helpers import genai_span_to_row
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
    NormalizedMessage,
)
from weave.trace_server.agents.types import (
    AgentConversationChatReq,
    AgentConversationSpansReq,
    AgentCustomAttrsSchemaReq,
    AgentGroupByRef,
    AgentSearchReq,
    AgentSignalFilter,
    AgentSortBy,
    AgentSpanGroupDistributionSpec,
    AgentSpanGroupFilter,
    AgentSpanMeasureSpec,
    AgentSpansQueryReq,
    AgentSpanStatsMetricSpec,
    AgentSpanStatsNumericBucketSpec,
    AgentSpanStatsReq,
    AgentSpanValueRef,
    AgentsQueryReq,
    AgentTraceChatReq,
    GenAIOTelExportReq,
    RatingCondition,
)
from weave.trace_server.base64_content_conversion import AUTO_CONVERSION_MIN_SIZE
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.interface.feedback_types import (
    AGENT_MONITOR_FEEDBACK_TYPE,
    AGENT_USER_FEEDBACK_TYPE,
)
from weave.trace_server.interface.query import Query
from weave.trace_server.opentelemetry.python_spans import StatusCode


def _make_span(project_id: str, **overrides: object) -> AgentSpanCHInsertable:
    """Create a span with sensible defaults. Override any field via kwargs."""
    defaults = {
        "project_id": project_id,
        "trace_id": uuid.uuid4().hex,
        "span_id": uuid.uuid4().hex,
        "span_name": "test-span",
        "started_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "ended_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "status_code": "OK",
        "operation_name": "chat",
        "agent_name": "test-agent",
        "provider_name": "openai",
        "request_model": "gpt-4o",
        "input_tokens": 100,
        "output_tokens": 50,
    }
    defaults.update(overrides)
    return AgentSpanCHInsertable(**defaults)


def _insert_spans(ch_client, spans: list[AgentSpanCHInsertable]) -> None:
    """Insert spans. The `messages` MV populates the search index as a
    side effect of this insert.
    """
    rows = [genai_span_to_row(s) for s in spans]
    ch_client.insert(
        "spans",
        data=rows,
        column_names=ALL_SPAN_INSERT_COLUMNS,
    )


# ---------------------------------------------------------------------------
# Test: ungrouped spans query
# ---------------------------------------------------------------------------


def test_spans_insert_and_query(ch_server):
    """Insert spans and query with filters (ungrouped mode)."""
    project_id = _make_project_id("spans")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(project_id, agent_name="agent-A", started_at=now),
        _make_span(
            project_id,
            agent_name="agent-A",
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            agent_name="agent-B",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # Query all
    res = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    assert res.total_count == 3
    assert len(res.spans) == 3
    assert res.groups == []

    # Filter by agent_name
    res_filtered = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$eq": [
                            {"$getField": "agent.name"},
                            {"$literal": "agent-A"},
                        ]
                    }
                }
            ),
        )
    )
    assert res_filtered.total_count == 2
    assert all(s.agent_name == "agent-A" for s in res_filtered.spans)


def test_eval_span_fields_are_queryable(ch_server):
    """Eval metadata is first-class span data, not custom attrs."""
    project_id = _make_project_id("eval_spans")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            eval_run_id="eval-run-1",
            eval_predict_and_score_call_id="pas-1",
            eval_kind="agent",
            eval_row_digest="row-a",
            eval_example_id="example-a",
            eval_trial_index=0,
            eval_evaluation_name="agent eval",
            started_at=now,
        ),
        _make_span(
            project_id,
            eval_run_id="eval-run-1",
            eval_predict_and_score_call_id="pas-2",
            eval_kind="agent",
            eval_row_digest="row-b",
            eval_example_id="example-b",
            eval_trial_index=1,
            eval_evaluation_name="agent eval",
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            eval_run_id="eval-run-2",
            eval_predict_and_score_call_id="pas-3",
            eval_kind="standard",
            eval_row_digest="row-c",
            eval_example_id="example-c",
            eval_trial_index=0,
            eval_evaluation_name="standard eval",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    run_1 = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$eq": [
                            {"$getField": "eval.run_id"},
                            {"$literal": "eval-run-1"},
                        ]
                    }
                }
            ),
            sort_by=[AgentSortBy(field="eval_trial_index", direction="asc")],
        )
    )
    assert run_1.total_count == 2
    assert [
        (
            span.eval_run_id,
            span.eval_predict_and_score_call_id,
            span.eval_kind,
            span.eval_row_digest,
            span.eval_example_id,
            span.eval_trial_index,
            span.eval_evaluation_name,
        )
        for span in run_1.spans
    ] == [
        ("eval-run-1", "pas-1", "agent", "row-a", "example-a", 0, "agent eval"),
        ("eval-run-1", "pas-2", "agent", "row-b", "example-b", 1, "agent eval"),
    ]

    grouped = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="field", key="eval.kind")],
            sort_by=[AgentSortBy(field="span_count", direction="desc")],
        )
    )
    assert grouped.total_count == 2
    assert {
        group.group_keys["eval_kind"]: group.span_count for group in grouped.groups
    } == {"agent": 2, "standard": 1}


def test_eval_trial_index_unset_reads_as_none(ch_server):
    """A span with no eval trial index reads back as None, not the -1 sentinel.

    ClickHouse stores -1 for an unset eval_trial_index (it can't hold NULL
    ints); the query layer must hide that internal sentinel from callers. A
    span that *does* set trial index 0 must still read back as 0.
    """
    project_id = _make_project_id("eval_trial_none")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        # No eval metadata at all: trial index defaults to the -1 sentinel.
        _make_span(project_id, agent_name="no-eval", started_at=now),
        # Explicit trial index 0 must survive as 0 (falsy but set).
        _make_span(
            project_id,
            agent_name="eval-trial-0",
            eval_run_id="eval-run-1",
            eval_trial_index=0,
            started_at=now + datetime.timedelta(seconds=1),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    trial_by_agent = {s.agent_name: s.eval_trial_index for s in res.spans}
    assert trial_by_agent == {"no-eval": None, "eval-trial-0": 0}


def test_eval_spans_filter_by_kind_and_predict_and_score_call(ch_server):
    """Promoted eval columns beyond eval_run_id are independently filterable.

    Covers eval.kind (the LowCardinality column) and
    eval.predict_and_score_call_id (isolating a single trial), so the query
    path is exercised past the single eval.run_id filter.
    """
    project_id = _make_project_id("eval_filters")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            eval_run_id="run-1",
            eval_kind="agent",
            eval_predict_and_score_call_id="pas-1",
            started_at=now,
        ),
        _make_span(
            project_id,
            eval_run_id="run-1",
            eval_kind="agent",
            eval_predict_and_score_call_id="pas-2",
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            eval_run_id="run-2",
            eval_kind="standard",
            eval_predict_and_score_call_id="pas-3",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    by_kind = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            query=Query.model_validate(
                {"$expr": {"$eq": [{"$getField": "eval.kind"}, {"$literal": "agent"}]}}
            ),
        )
    )
    assert by_kind.total_count == 2
    assert {s.eval_predict_and_score_call_id for s in by_kind.spans} == {
        "pas-1",
        "pas-2",
    }

    by_pas = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$eq": [
                            {"$getField": "eval.predict_and_score_call_id"},
                            {"$literal": "pas-2"},
                        ]
                    }
                }
            ),
        )
    )
    assert by_pas.total_count == 1
    assert by_pas.spans[0].eval_run_id == "run-1"
    assert by_pas.spans[0].eval_kind == "agent"


def test_insert_spans_bulk_writes_all_in_one_call(ch_server):
    """`AgentWriteHandler.insert_spans` bulk-writes every span in one insert
    (the scoring-worker batch path); empty input is a no-op.
    """
    project_id = _make_project_id("bulk_spans")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    spans = [
        _make_span(project_id, agent_name="bulk-A", started_at=now),
        _make_span(
            project_id,
            agent_name="bulk-B",
            started_at=now + datetime.timedelta(seconds=1),
        ),
    ]
    handler = AgentWriteHandler(ch_server.ch_client)
    handler.insert_spans([])  # no-op
    handler.insert_spans(spans)

    res = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    assert res.total_count == 2
    assert {s.agent_name for s in res.spans} == {"bulk-A", "bulk-B"}


# ---------------------------------------------------------------------------
# Test: read-time trace attribution of agent / conversation identity
# ---------------------------------------------------------------------------


def _agent_name_eq(value: str) -> Query:
    return Query.model_validate(
        {"$expr": {"$eq": [{"$getField": "agent.name"}, {"$literal": value}]}}
    )


def test_unset_span_inherits_identity_from_its_trace(ch_server):
    """A child span with no direct agent metadata inherits it from its turn.

    Identity is reported only on the `invoke_agent` span, while the child llm
    span carries no agent_name. The spans query reads from the attributed
    source, so the child both *displays* and *filters as* the turn's agent —
    while a span from an unrelated trace is never pulled in.
    """
    project_id = _make_project_id("attribution")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    trace_id = uuid.uuid4().hex
    invoke_span_id = uuid.uuid4().hex
    child_span_id = uuid.uuid4().hex
    other_span_id = uuid.uuid4().hex

    spans = [
        # invoke_agent span carries the agent identity.
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=invoke_span_id,
            operation_name="invoke_agent",
            agent_name="Planner",
            started_at=now,
        ),
        # child llm span has NO direct agent metadata; it should inherit.
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=child_span_id,
            parent_span_id=invoke_span_id,
            operation_name="chat",
            agent_name="",
            started_at=now + datetime.timedelta(seconds=1),
        ),
        # unrelated trace / agent — must never be pulled in.
        _make_span(
            project_id,
            trace_id=uuid.uuid4().hex,
            span_id=other_span_id,
            agent_name="OtherAgent",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # Unfiltered list: the child *displays* the inherited agent name.
    listed = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    by_id = {s.span_id: s for s in listed.spans}
    assert by_id[child_span_id].agent_name == "Planner"
    assert by_id[invoke_span_id].agent_name == "Planner"
    assert by_id[other_span_id].agent_name == "OtherAgent"

    # Filtering on the agent matches the whole turn (own + inherited), and
    # nothing from the unrelated trace.
    matched = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, query=_agent_name_eq("Planner"))
    )
    assert matched.total_count == 2
    assert {s.span_id for s in matched.spans} == {invoke_span_id, child_span_id}

    # Time-bounded query: the fallback scan is slack-widened to the same window
    # and still attributes the child span.
    windowed = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            started_after=now - datetime.timedelta(minutes=1),
            started_before=now + datetime.timedelta(minutes=1),
            query=_agent_name_eq("Planner"),
        )
    )
    assert {s.span_id for s in windowed.spans} == {invoke_span_id, child_span_id}


def test_span_with_own_identity_is_not_reattributed(ch_server):
    """A span that sets its own agent identity keeps it (singleton).

    In a multi-agent turn, a sub-agent span that reported its own agent_name
    must not be pulled into the parent agent's filter, and must not be displayed
    as the parent agent.
    """
    project_id = _make_project_id("attribution_singleton")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    trace_id = uuid.uuid4().hex
    coordinator_span_id = uuid.uuid4().hex
    worker_span_id = uuid.uuid4().hex

    spans = [
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=coordinator_span_id,
            operation_name="invoke_agent",
            agent_name="Coordinator",
            started_at=now,
        ),
        # Sub-agent span reports its OWN agent_name.
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=worker_span_id,
            parent_span_id=coordinator_span_id,
            operation_name="invoke_agent",
            agent_name="Worker",
            started_at=now + datetime.timedelta(seconds=1),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # The sub-agent span keeps its own identity on display.
    listed = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    by_id = {s.span_id: s for s in listed.spans}
    assert by_id[worker_span_id].agent_name == "Worker"
    assert by_id[coordinator_span_id].agent_name == "Coordinator"

    # Filtering for the sub-agent returns only its own span, not the parent's.
    worker = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, query=_agent_name_eq("Worker"))
    )
    assert {s.span_id for s in worker.spans} == {worker_span_id}

    # Filtering for the parent does not pull in the self-identified sub-agent.
    coordinator = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, query=_agent_name_eq("Coordinator"))
    )
    assert {s.span_id for s in coordinator.spans} == {coordinator_span_id}


def _identity(span: object) -> tuple[str, str, str, str]:
    return (
        span.agent_name,
        span.agent_version,
        span.agent_id,
        span.conversation_id,
    )


def test_two_pass_list_attribution_matches_full_attribution(ch_server):
    """The page-prefetch two-pass attributes a span exactly like the full path.

    A plain list (non-identity sort/filter) limits first then attributes only
    the page, scoping the fallback to the page's traces. This must produce the
    same per-span identity as the full-attribution path, even when the page
    straddles a trace boundary: a child span on the page inherits the identity
    of its trace's earliest agent span *even when that span is off the page*,
    because the fallback is scoped by trace_id, not by the page's rows.
    """
    project_id = _make_project_id("two_pass_attr")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    tx, ty, tq = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex

    def sid() -> str:
        return uuid.uuid4().hex

    root_x, own_z, child_x = sid(), sid(), sid()
    root_y, child_y, q = sid(), sid(), sid()

    def at(secs: int) -> datetime.datetime:
        return now + datetime.timedelta(seconds=secs)

    spans = [
        # Trace TX: earliest span (root_x) declares Delta; a later sub-agent span
        # (own_z) declares its own Zeta; the latest span (child_x) is unset and
        # must inherit Delta. Sorted started_at DESC, root_x is LAST -> a small
        # page that includes child_x excludes root_x (the straddle case).
        _make_span(
            project_id,
            trace_id=tx,
            span_id=root_x,
            operation_name="invoke_agent",
            agent_name="Delta",
            agent_version="dv",
            agent_id="did",
            conversation_id="cx",
            started_at=at(1),
        ),
        _make_span(
            project_id,
            trace_id=tx,
            span_id=own_z,
            operation_name="invoke_agent",
            agent_name="Zeta",
            agent_version="zv",
            agent_id="zid",
            conversation_id="",
            started_at=at(99),
        ),
        _make_span(
            project_id,
            trace_id=tx,
            span_id=child_x,
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            started_at=at(100),
        ),
        # Trace TY: root + inheriting child, both recent (fully on a small page).
        _make_span(
            project_id,
            trace_id=ty,
            span_id=root_y,
            operation_name="invoke_agent",
            agent_name="Epsilon",
            agent_version="ev",
            agent_id="eid",
            conversation_id="cy",
            started_at=at(101),
        ),
        _make_span(
            project_id,
            trace_id=ty,
            span_id=child_y,
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            started_at=at(102),
        ),
        # Trace TQ: a lone unset span, no identity-bearing span in its trace, so
        # it stays blank under both paths.
        _make_span(
            project_id,
            trace_id=tq,
            span_id=q,
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            started_at=at(50),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # Two-pass (default started_at DESC sort, non-identity -> two-pass).
    two_pass = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    tp = {s.span_id: _identity(s) for s in two_pass.spans}

    # The attribution rule, computed independently of the query.
    assert tp[root_x] == ("Delta", "dv", "did", "cx")
    assert tp[child_x] == ("Delta", "dv", "did", "cx")  # inherits root_x's triple
    assert tp[own_z] == ("Zeta", "zv", "zid", "cx")  # own triple, conv inherited
    assert tp[root_y] == ("Epsilon", "ev", "eid", "cy")
    assert tp[child_y] == ("Epsilon", "ev", "eid", "cy")
    assert tp[q] == ("", "", "", "")

    # Full-attribution path (identity sort gates out of two-pass) attributes
    # every span identically; compared by span_id so the sort order is moot.
    full = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            sort_by=[AgentSortBy(field="agent_name", direction="asc")],
        )
    )
    assert {s.span_id: _identity(s) for s in full.spans} == tp

    # Straddle: a page of 3 (started_at DESC) is [child_y, root_y, child_x].
    # child_x inherits Delta even though its source span root_x is off the page.
    page = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, limit=3)
    )
    assert [s.span_id for s in page.spans] == [child_y, root_y, child_x]
    assert all(_identity(s) == tp[s.span_id] for s in page.spans)


def test_two_pass_page_cut_inside_started_at_tie(ch_server):
    """When the page cut falls inside a `started_at` tie, the `span_id`
    tiebreaker gives a well-defined page and inheritance holds across the cut.

    The two-pass references the page twice (base relation + the fallback's
    trace_id scope); a `started_at`-only order is not total, so the page is
    contractually defined only once `span_id` completes the sort key (see the
    SQL snapshot tests for the tiebreaker itself). Here the cut splits a tie and
    a child's identity-bearing root sorts below it, so the page takes the child
    but not the root; the trace_id-scoped fallback still attributes it.
    """
    project_id = _make_project_id("two_pass_ties")
    tied = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)

    # All spans share one `started_at`; `span_id DESC` alone orders the page.
    # t1's root sorts BELOW its child, so a page of 3 takes the child and cuts
    # the root off (straddle within the tie); t1's child must still inherit.
    spans = [
        _make_span(
            project_id,
            trace_id="t1",
            span_id="t1_root",
            operation_name="invoke_agent",
            agent_name="Gamma",
            agent_version="gv",
            agent_id="gid",
            conversation_id="cg",
            started_at=tied,
        ),
        _make_span(
            project_id,
            trace_id="t1",
            span_id="t1_zchild",
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            started_at=tied,
        ),
        _make_span(
            project_id,
            trace_id="t2",
            span_id="t2_root",
            operation_name="invoke_agent",
            agent_name="Theta",
            agent_version="tv",
            agent_id="tid",
            conversation_id="ct",
            started_at=tied,
        ),
        _make_span(
            project_id,
            trace_id="t2",
            span_id="t2_zchild",
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            started_at=tied,
        ),
        _make_span(
            project_id,
            trace_id="f0",
            span_id="f0",
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            started_at=tied,
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # span_id DESC over the tie: t2_zchild, t2_root, t1_zchild, t1_root, f0.
    page = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, limit=3)
    )
    assert [s.span_id for s in page.spans] == ["t2_zchild", "t2_root", "t1_zchild"]
    ident = {s.span_id: _identity(s) for s in page.spans}
    assert ident["t2_zchild"] == ("Theta", "tv", "tid", "ct")
    assert ident["t2_root"] == ("Theta", "tv", "tid", "ct")
    # The straddle-in-tie span: inherits Gamma though t1_root is below the cut.
    assert ident["t1_zchild"] == ("Gamma", "gv", "gid", "cg")


def test_two_pass_inherits_root_outside_window_via_slack(ch_server):
    """The two-pass fallback widens by slack, so an in-window child inherits an
    identity-bearing root that started just before the query window.

    The page base scan is bounded to the window (the root is off-page), but the
    trace_id-scoped fallback rollup widens the window by one trace-duration, so
    the root still resolves and the child inherits across the window edge.
    """
    project_id = _make_project_id("two_pass_slack")
    after = datetime.datetime(2026, 4, 1, 12, 0, tzinfo=datetime.timezone.utc)
    before = after + datetime.timedelta(minutes=10)

    # root starts 5min before the window (inside the 1h fallback slack); child
    # starts inside the window. A lone in-window span anchors the page.
    spans = [
        _make_span(
            project_id,
            trace_id="t1",
            span_id="root",
            operation_name="invoke_agent",
            agent_name="Sigma",
            agent_version="sv",
            agent_id="sid",
            conversation_id="cs",
            started_at=after - datetime.timedelta(minutes=5),
        ),
        _make_span(
            project_id,
            trace_id="t1",
            span_id="child",
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            started_at=after + datetime.timedelta(minutes=1),
        ),
        _make_span(
            project_id,
            trace_id="t2",
            span_id="other",
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            started_at=after + datetime.timedelta(minutes=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    page = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id, started_after=after, started_before=before
        )
    )
    by_id = {s.span_id: _identity(s) for s in page.spans}
    # root is off-page (outside the window) but still resolves the child.
    assert "root" not in by_id
    assert by_id["child"] == ("Sigma", "sv", "sid", "cs")
    assert by_id["other"] == ("", "", "", "")


def test_two_pass_include_costs_matches_full_attribution(ch_server):
    """include_costs two-pass joins prices to the page; per-span costs equal the
    full-attribution path, the cost is span-exact (a child's own tokens, not the
    inherited agent's), and an unpriced model passes through as null cost.
    """
    project_id = _make_project_id("two_pass_costs")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    tx = uuid.uuid4().hex
    root, child, lone = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex

    def at(secs: int) -> datetime.datetime:
        return now + datetime.timedelta(seconds=secs)

    spans = [
        _make_span(
            project_id,
            trace_id=tx,
            span_id=root,
            operation_name="invoke_agent",
            agent_name="Delta",
            agent_version="dv",
            agent_id="did",
            conversation_id="cx",
            request_model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            started_at=at(1),
        ),
        _make_span(
            project_id,
            trace_id=tx,
            span_id=child,
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            request_model="gpt-4o",
            input_tokens=200,
            output_tokens=100,
            started_at=at(2),
        ),
        _make_span(
            project_id,
            trace_id=uuid.uuid4().hex,
            span_id=lone,
            operation_name="chat",
            agent_name="",
            agent_version="",
            agent_id="",
            conversation_id="",
            request_model="no-such-model-xyz",
            input_tokens=10,
            output_tokens=10,
            started_at=at(3),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    tp = {
        s.span_id: s
        for s in ch_server.agent_spans_query(
            AgentSpansQueryReq(project_id=project_id, include_costs=True)
        ).spans
    }
    # A cost-column sort gates out of the two-pass -> the full-attribution path.
    full = {
        s.span_id: s
        for s in ch_server.agent_spans_query(
            AgentSpansQueryReq(
                project_id=project_id,
                include_costs=True,
                sort_by=[AgentSortBy(field="total_cost_usd", direction="desc")],
            )
        ).spans
    }

    def costs(s: object) -> tuple:
        return (s.input_cost_usd, s.output_cost_usd, s.total_cost_usd)

    for sid in (root, child, lone):
        assert costs(tp[sid]) == costs(full[sid])
        assert _identity(tp[sid]) == _identity(full[sid])

    # Priced spans get real costs; the child's cost is its own (200/100 tokens),
    # not the inherited agent's (1000/500), while its identity IS inherited.
    assert tp[root].total_cost_usd
    assert tp[child].total_cost_usd
    assert tp[child].total_cost_usd != tp[root].total_cost_usd
    assert _identity(tp[child]) == ("Delta", "dv", "did", "cx")
    # An unpriced model stays null (distinguishes "unpriced" from "free").
    assert tp[lone].total_cost_usd is None


def test_unset_span_inherits_a_coherent_agent_triple(ch_server):
    """An inherited identity is one real agent, never a mix of two.

    agent_name / agent_version / agent_id identify one agent, so an unset span
    inherits all three from a single span (the earliest in its trace that
    declares an agent_name). Here two identity-bearing spans deliberately split
    the columns — one carries the name, a later one carries a version — so a
    per-column inheritance would synthesize the (name, version) pair
    ('Planner', 'v2') that never existed on any span. The child must instead
    inherit Planner's own (coherent) triple.
    """
    project_id = _make_project_id("attribution_coherent")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    trace_id = uuid.uuid4().hex
    planner_span_id = uuid.uuid4().hex
    versioned_span_id = uuid.uuid4().hex
    child_span_id = uuid.uuid4().hex

    spans = [
        # Earliest identity-bearing span: name set, version blank.
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=planner_span_id,
            operation_name="invoke_agent",
            agent_name="Planner",
            agent_version="",
            started_at=now,
        ),
        # A later span carries a version but no name.
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=versioned_span_id,
            operation_name="invoke_agent",
            agent_name="",
            agent_version="v2",
            started_at=now + datetime.timedelta(seconds=1),
        ),
        # Unset child: must inherit Planner's whole triple, not a mix.
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=child_span_id,
            parent_span_id=planner_span_id,
            operation_name="chat",
            agent_name="",
            agent_version="",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    listed = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    child = {s.span_id: s for s in listed.spans}[child_span_id]
    # Coherent: the inherited (name, version) co-occurred on a real span.
    assert (child.agent_name, child.agent_version) == ("Planner", "")

    # And filtering on the phantom pair must not pull the child in.
    phantom = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$and": [
                            {
                                "$eq": [
                                    {"$getField": "agent.name"},
                                    {"$literal": "Planner"},
                                ]
                            },
                            {
                                "$eq": [
                                    {"$getField": "agent.version"},
                                    {"$literal": "v2"},
                                ]
                            },
                        ]
                    }
                }
            ),
        )
    )
    assert phantom.spans == []


# ---------------------------------------------------------------------------
# Test: group by trace_id (replaces old traces_query)
# ---------------------------------------------------------------------------


def test_group_by_trace_id(ch_server):
    """Grouping spans by trace_id returns per-trace aggregates."""
    project_id = _make_project_id("traces")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    trace_a = uuid.uuid4().hex
    trace_b = uuid.uuid4().hex

    spans = [
        # Trace A: 2 spans, 300 input tokens total
        _make_span(
            project_id,
            trace_id=trace_a,
            input_tokens=100,
            output_tokens=20,
            agent_name="alpha",
            started_at=now,
        ),
        _make_span(
            project_id,
            trace_id=trace_a,
            input_tokens=200,
            output_tokens=30,
            agent_name="alpha",
            started_at=now + datetime.timedelta(seconds=1),
        ),
        # Trace B: 1 span
        _make_span(
            project_id,
            trace_id=trace_b,
            input_tokens=50,
            output_tokens=10,
            agent_name="beta",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="column", key="trace_id")],
        )
    )
    assert res.total_count == 2
    assert res.spans == []

    by_trace = {g.group_keys["trace_id"]: g for g in res.groups}
    assert by_trace[trace_a].span_count == 2
    assert by_trace[trace_a].total_input_tokens == 300
    assert by_trace[trace_a].total_output_tokens == 50
    assert "alpha" in by_trace[trace_a].agent_names

    assert by_trace[trace_b].span_count == 1
    assert by_trace[trace_b].total_input_tokens == 50


# ---------------------------------------------------------------------------
# Test: group by conversation_id (replaces old conversations_query)
# ---------------------------------------------------------------------------


# flaky: CI ClickHouse occasionally doesn't surface the just-inserted spans to the immediate read.
@pytest.mark.flaky(reruns=3)
def test_group_by_conversation_id(ch_server):
    """Grouping spans by conversation_id returns per-conversation aggregates."""
    project_id = _make_project_id("convs")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    conv_a = f"conv-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-{uuid.uuid4().hex[:8]}"

    spans = [
        _make_span(
            project_id,
            conversation_id=conv_a,
            conversation_name="Alpha Chat",
            operation_name="invoke_agent",
            agent_name="agent-x",
            cache_creation_input_tokens=3,
            cache_read_input_tokens=7,
            reasoning_tokens=13,
            started_at=now,
        ),
        _make_span(
            project_id,
            conversation_id=conv_a,
            conversation_name="Alpha Chat",
            operation_name="chat",
            agent_name="agent-x",
            cache_creation_input_tokens=5,
            cache_read_input_tokens=11,
            reasoning_tokens=17,
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            conversation_name="Beta Chat",
            operation_name="invoke_agent",
            agent_name="agent-y",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
        )
    )
    # Only inserted rows have our conversation_ids, but project may include
    # a row with the default empty conversation_id from other tests; guard
    # by filtering to the conversation_ids we actually created.
    by_conv = {g.group_keys["conversation_id"]: g for g in res.groups}
    assert conv_a in by_conv
    assert conv_b in by_conv

    assert by_conv[conv_a].span_count == 2
    assert by_conv[conv_a].invocation_count == 1  # one invoke_agent span
    assert by_conv[conv_a].total_cache_creation_input_tokens == 8
    assert by_conv[conv_a].total_cache_read_input_tokens == 18
    assert by_conv[conv_a].total_reasoning_tokens == 30
    assert "agent-x" in by_conv[conv_a].agent_names
    assert "Alpha Chat" in by_conv[conv_a].conversation_names

    assert by_conv[conv_b].span_count == 1
    assert by_conv[conv_b].invocation_count == 1
    assert "agent-y" in by_conv[conv_b].agent_names
    assert "Beta Chat" in by_conv[conv_b].conversation_names


def test_group_by_conversation_id_message_previews(ch_server):
    """Grouped conversation rows carry first/last message previews computed via
    argMin/argMax over the spans — no per-row hydration needed.

    Validates the real ClickHouse aggregate semantics: empty turn-1 spans are
    skipped, the earliest message-bearing span's opening user prompt becomes
    `first_message`, and the latest span's assistant output becomes
    `last_message`.
    """
    project_id = _make_project_id("conv-previews")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    conv = f"conv-{uuid.uuid4().hex[:8]}"

    spans = [
        # Turn-1 span with no messages. It must be skipped by the -If guard
        # before selecting first_input_messages.
        _make_span(
            project_id,
            conversation_id=conv,
            operation_name="invoke_agent",
            started_at=now,
            ended_at=now + datetime.timedelta(seconds=1),
            input_messages=[],
            output_messages=[],
        ),
        _make_span(
            project_id,
            conversation_id=conv,
            operation_name="execute_tool",
            started_at=now + datetime.timedelta(seconds=2),
            ended_at=now + datetime.timedelta(seconds=3),
            input_messages=[],
            output_messages=[],
        ),
        # Earliest span with messages: accumulated history starts at the
        # opening, even though the current turn's user text is the last entry.
        _make_span(
            project_id,
            conversation_id=conv,
            operation_name="chat",
            started_at=now + datetime.timedelta(seconds=4),
            ended_at=now + datetime.timedelta(seconds=5),
            input_messages=[
                NormalizedMessage(role="user", content="opening"),
                NormalizedMessage(role="assistant", content="r1"),
                NormalizedMessage(role="user", content="follow-up"),
            ],
            output_messages=[
                NormalizedMessage(role="assistant", content="final reply")
            ],
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
        )
    )
    by_conv = {g.group_keys["conversation_id"]: g for g in res.groups}
    assert conv in by_conv
    row = by_conv[conv]

    assert row.first_message is not None
    assert row.first_message.role == "user_message"
    assert row.first_message.text == "opening"

    assert row.last_message is not None
    assert row.last_message.role == "assistant_message"
    assert row.last_message.text == "final reply"


def _create_feedback(
    ch_server,
    project_id: str,
    weave_ref: str,
    feedback_type: str,
    payload: dict | None = None,
    **scorer_fields,
) -> None:
    ch_server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type=feedback_type,
            payload=payload or {},
            wb_user_id="test-user",
            **scorer_fields,
        )
    )


def test_conversation_spans_unknown_id_returns_empty(ch_server):
    """The endpoint returns one entry per requested conversation; an id with no
    matching spans comes back with empty sequences rather than being dropped.
    """
    project_id = _make_project_id("conv-spans-empty")
    res = ch_server.agent_conversation_spans(
        AgentConversationSpansReq(
            project_id=project_id,
            conversation_ids=["conv-does-not-exist"],
        )
    )
    assert len(res.conversations) == 1
    assert res.conversations[0].conversation_id == "conv-does-not-exist"
    assert res.conversations[0].spans == []
    assert res.conversations[0].spans_feedback == []


def test_conversation_spans_sequence_and_feedback(ch_server):
    """agent_conversation_spans returns an ordered per-span sequence (kinds from
    operation_name, ERROR surfaced via status) plus turn-anchored feedback
    markers carrying detoned tags and scorer ratings.
    """
    project_id = _make_project_id("conv-spans")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    conv = f"conv-{uuid.uuid4().hex[:8]}"
    trace_a = uuid.uuid4().hex
    trace_b = uuid.uuid4().hex
    tool_span = uuid.uuid4().hex[:16]

    spans = [
        # Turn A: an agent invocation, then two tool calls (the second errored).
        _make_span(
            project_id,
            conversation_id=conv,
            trace_id=trace_a,
            operation_name="invoke_agent",
            started_at=now,
            ended_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            conversation_id=conv,
            trace_id=trace_a,
            span_id=tool_span,
            operation_name="execute_tool",
            tool_name="search",
            started_at=now + datetime.timedelta(seconds=2),
            ended_at=now + datetime.timedelta(seconds=3),
        ),
        _make_span(
            project_id,
            conversation_id=conv,
            trace_id=trace_a,
            operation_name="execute_tool",
            tool_name="broken",
            status_code="ERROR",
            started_at=now + datetime.timedelta(seconds=4),
            ended_at=now + datetime.timedelta(seconds=5),
        ),
        # Turn B: a later content span -> classified assistant.
        _make_span(
            project_id,
            conversation_id=conv,
            trace_id=trace_b,
            operation_name="chat",
            started_at=now + datetime.timedelta(seconds=6),
            ended_at=now + datetime.timedelta(seconds=7),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # Turn A: a human thumbs-up tag. Turn B: a scorer with a tag + a rating.
    turn_a_ref = ri.InternalAgentTurnRef(project_id=project_id, trace_id=trace_a).uri
    turn_b_ref = ri.InternalAgentTurnRef(project_id=project_id, trace_id=trace_b).uri
    _create_feedback(
        ch_server,
        project_id,
        turn_a_ref,
        AGENT_USER_FEEDBACK_TYPE,
        scorer_tags=["\U0001f44d"],
    )
    _create_feedback(
        ch_server,
        project_id,
        turn_b_ref,
        AGENT_MONITOR_FEEDBACK_TYPE,
        runnable_ref=ri.InternalOpRef(
            project_id=project_id, name="quality_scorer", version="v1"
        ).uri,
        call_ref=ri.InternalCallRef(project_id=project_id, id=trace_b).uri,
        trigger_ref=ri.InternalObjectRef(
            project_id=project_id, name="quality_scorer_trigger", version="v1"
        ).uri,
        scorer_tags=["helpful"],
        scorer_ratings={"quality": 0.8},
        scorer_rating_reasons={"quality": "clear answer"},
    )
    res = ch_server.agent_conversation_spans(
        AgentConversationSpansReq(
            project_id=project_id,
            conversation_ids=[conv],
        )
    )
    row = {c.conversation_id: c for c in res.conversations}[conv]

    # Spans carry the raw operation_name (the client classifies), ordered by
    # started_at; ERROR surfaces via status.
    assert [(e.operation_name, e.status) for e in row.spans] == [
        ("invoke_agent", "OK"),
        ("execute_tool", "OK"),
        ("execute_tool", "ERROR"),
        ("chat", "OK"),
    ]
    # Each span carries its turn (trace_id) and its own span_id.
    assert row.spans[0].trace_id == trace_a
    assert row.spans[-1].trace_id == trace_b
    assert any(e.span_id == tool_span for e in row.spans)

    # Markers are keyed by turn (trace_id). Emoji tags come back as the detoned
    # glyph; scorer ratings come back as ratings.
    by_trace = {f.trace_id: f for f in row.spans_feedback}
    assert by_trace[trace_a].feedback_type == AGENT_USER_FEEDBACK_TYPE
    assert by_trace[trace_a].tags == ["👍"]
    assert by_trace[trace_a].ratings == []

    assert by_trace[trace_b].feedback_type == AGENT_MONITOR_FEEDBACK_TYPE
    assert by_trace[trace_b].tags == ["helpful"]
    assert len(by_trace[trace_b].ratings) == 1
    rating = by_trace[trace_b].ratings[0]
    assert (rating.name, rating.value, rating.reason) == (
        "quality",
        0.8,
        "clear answer",
    )


def test_group_by_conversation_id_filters_numeric_aggregates(ch_server):
    """Grouped conversation queries support server-side aggregate range filters."""
    project_id = _make_project_id("convs_num")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    conv_a = f"conv-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-{uuid.uuid4().hex[:8]}"

    spans = [
        _make_span(project_id, conversation_id=conv_a, started_at=now),
        _make_span(
            project_id,
            conversation_id=conv_a,
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
            group_filters=[
                AgentSpanGroupFilter(
                    measure=AgentSpanMeasureSpec(
                        alias="span_count",
                        aggregation="count",
                    ),
                    min=2,
                ),
            ],
        )
    )

    by_conv = {g.group_keys["conversation_id"]: g for g in res.groups}
    assert conv_a in by_conv
    assert conv_b not in by_conv
    assert res.total_count == 1


def test_group_by_conversation_id_custom_attr_measures(ch_server):
    """Conversation groups return built-in aggregates plus custom attr metrics."""
    project_id = _make_project_id("convs_cattr_metrics")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    conv_a = f"conv-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-{uuid.uuid4().hex[:8]}"
    avg_score = AgentSpanMeasureSpec(
        alias="custom_float_score_avg",
        aggregation="avg",
        value=AgentSpanValueRef(source="custom_attrs_float", key="score"),
        value_type="number",
    )

    spans = [
        _make_span(
            project_id,
            conversation_id=conv_a,
            conversation_name="Alpha Chat",
            custom_attrs_float={"score": 0.9},
            custom_attrs_bool={"cached": True},
            custom_attrs_string={"env": "prod"},
            started_at=now,
        ),
        _make_span(
            project_id,
            conversation_id=conv_a,
            conversation_name="Alpha Chat",
            custom_attrs_float={"score": 0.7},
            custom_attrs_bool={"cached": False},
            custom_attrs_string={"env": "prod"},
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            conversation_name="Beta Chat",
            custom_attrs_float={"score": 0.2},
            custom_attrs_bool={"cached": False},
            custom_attrs_string={"env": "dev"},
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
            measures=[
                avg_score,
                AgentSpanMeasureSpec(
                    alias="custom_bool_cached_true",
                    aggregation="count_true",
                    value=AgentSpanValueRef(source="custom_attrs_bool", key="cached"),
                ),
                AgentSpanMeasureSpec(
                    alias="custom_string_env_distinct",
                    aggregation="count_distinct",
                    value=AgentSpanValueRef(source="custom_attrs_string", key="env"),
                ),
            ],
            group_filters=[AgentSpanGroupFilter(measure=avg_score, min=0.7)],
            sort_by=[
                AgentSortBy(field="custom_float_score_avg", direction="desc"),
            ],
        )
    )

    assert res.total_count == 1
    assert len(res.groups) == 1
    row = res.groups[0]
    assert row.group_keys["conversation_id"] == conv_a
    assert row.span_count == 2
    assert row.conversation_names == ["Alpha Chat"]
    assert abs(float(row.metrics["custom_float_score_avg"]) - 0.8) < 0.0001
    assert row.metrics["custom_bool_cached_true"] == 1
    assert row.metrics["custom_string_env_distinct"] == 1


def test_conversation_custom_attr_distributions(ch_server):
    """Grouped spans query returns custom attr distributions by conversation."""
    project_id = _make_project_id("convs_cattr_dists")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    conv_a = f"conv-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-{uuid.uuid4().hex[:8]}"

    spans = [
        _make_span(
            project_id,
            conversation_id=conv_a,
            custom_attrs_float={"score": 0.1},
            custom_attrs_int={"latency": 10},
            custom_attrs_string={"env": "prod"},
            custom_attrs_bool={"cached": True},
            started_at=now,
        ),
        _make_span(
            project_id,
            conversation_id=conv_a,
            custom_attrs_float={"score": 0.9},
            custom_attrs_int={"latency": 30},
            custom_attrs_string={"env": "prod"},
            custom_attrs_bool={"cached": False},
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            conversation_id=conv_a,
            custom_attrs_string={"env": "dev"},
            started_at=now + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            custom_attrs_float={"score": 0.4},
            custom_attrs_int={"latency": 20},
            custom_attrs_string={"env": "staging"},
            custom_attrs_bool={"cached": True},
            started_at=now + datetime.timedelta(seconds=3),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
            group_distributions=[
                AgentSpanGroupDistributionSpec(
                    alias="custom_float_score_distribution",
                    value=AgentSpanValueRef(source="custom_attrs_float", key="score"),
                    bins=2,
                ),
                AgentSpanGroupDistributionSpec(
                    alias="custom_int_latency_distribution",
                    value=AgentSpanValueRef(source="custom_attrs_int", key="latency"),
                    bins=2,
                ),
                AgentSpanGroupDistributionSpec(
                    alias="custom_string_env_distribution",
                    value=AgentSpanValueRef(source="custom_attrs_string", key="env"),
                    top_n=2,
                ),
                AgentSpanGroupDistributionSpec(
                    alias="custom_bool_cached_distribution",
                    value=AgentSpanValueRef(source="custom_attrs_bool", key="cached"),
                    top_n=2,
                ),
            ],
        )
    )

    by_conversation = {row.group_keys["conversation_id"]: row for row in res.groups}

    score_a = by_conversation[conv_a].distributions["custom_float_score_distribution"]
    assert score_a.total_count == 3
    assert score_a.present_count == 2
    assert score_a.missing_count == 1
    assert [bin.count for bin in score_a.bins] == [1, 1]
    assert score_a.bins[0].min == 0.1
    assert score_a.bins[-1].max == 0.9

    latency_a = by_conversation[conv_a].distributions["custom_int_latency_distribution"]
    assert latency_a.total_count == 3
    assert latency_a.present_count == 2
    assert latency_a.missing_count == 1
    assert [bin.count for bin in latency_a.bins] == [1, 1]
    assert latency_a.bins[0].min == 10
    assert latency_a.bins[-1].max == 30

    env_a = by_conversation[conv_a].distributions["custom_string_env_distribution"]
    assert env_a.present_count == 3
    assert env_a.other_count == 0
    assert [(value.value, value.count) for value in env_a.values] == [
        ("prod", 2),
        ("dev", 1),
    ]

    cached_a = by_conversation[conv_a].distributions["custom_bool_cached_distribution"]
    assert cached_a.present_count == 2
    assert cached_a.missing_count == 1
    assert [(value.value, value.count) for value in cached_a.values] == [
        ("false", 1),
        ("true", 1),
    ]

    score_b = by_conversation[conv_b].distributions["custom_float_score_distribution"]
    assert score_b.total_count == 1
    assert score_b.present_count == 1
    assert len(score_b.bins) == 1
    assert score_b.bins[0].count == 1

    latency_b = by_conversation[conv_b].distributions["custom_int_latency_distribution"]
    assert latency_b.total_count == 1
    assert latency_b.present_count == 1
    assert len(latency_b.bins) == 1
    assert latency_b.bins[0].count == 1


# ---------------------------------------------------------------------------
# Test: group by a custom_attrs_string map key (the new capability)
# ---------------------------------------------------------------------------


def test_group_by_custom_attrs(ch_server):
    """Grouping on a custom_attrs_string key buckets spans by the user-supplied label."""
    project_id = _make_project_id("cattr")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            agent_name="a1",
            custom_attrs_string={"env": "prod"},
            input_tokens=100,
            started_at=now,
        ),
        _make_span(
            project_id,
            agent_name="a1",
            custom_attrs_string={"env": "prod"},
            input_tokens=200,
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            agent_name="a1",
            custom_attrs_string={"env": "staging"},
            input_tokens=50,
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[
                AgentGroupByRef(source="custom_attrs_string", key="env"),
            ],
        )
    )
    by_env = {g.group_keys["env"]: g for g in res.groups}
    assert by_env["prod"].span_count == 2
    assert by_env["prod"].total_input_tokens == 300
    assert by_env["staging"].span_count == 1
    assert by_env["staging"].total_input_tokens == 50


def test_custom_attrs_schema_discovers_keys_types_and_counts(ch_server):
    """Schema discovery returns typed keys without hydrating custom attr values."""
    project_id = _make_project_id("cattr_schema")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            agent_name="alpha",
            custom_attrs_string={"env": "prod", "payload": "x" * 10_000},
            custom_attrs_float={"score": 0.8},
            custom_attrs_bool={"cached": True},
            started_at=now,
        ),
        _make_span(
            project_id,
            agent_name="alpha",
            custom_attrs_string={"env": "staging"},
            custom_attrs_int={"retries": 2},
            custom_attrs_float={"score": 0.4},
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            agent_name="beta",
            custom_attrs_string={"env": "prod"},
            custom_attrs_int={"retries": 1},
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_custom_attrs_schema(
        AgentCustomAttrsSchemaReq(project_id=project_id)
    )

    by_source_key = {(attr.source, attr.key): attr for attr in res.attributes}
    assert by_source_key["custom_attrs_string", "env"].value_type == "string"
    assert by_source_key["custom_attrs_string", "env"].span_count == 3
    assert by_source_key["custom_attrs_float", "score"].value_type == "float"
    assert by_source_key["custom_attrs_float", "score"].span_count == 2
    assert by_source_key["custom_attrs_int", "retries"].value_type == "int"
    assert by_source_key["custom_attrs_int", "retries"].span_count == 2
    assert by_source_key["custom_attrs_bool", "cached"].value_type == "bool"
    assert by_source_key["custom_attrs_bool", "cached"].span_count == 1
    assert by_source_key["custom_attrs_string", "payload"].span_count == 1
    assert res.limit == 200
    assert res.offset == 0
    assert res.has_more is False

    filtered = ch_server.agent_custom_attrs_schema(
        AgentCustomAttrsSchemaReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$eq": [
                            {"$getField": "agent.name"},
                            {"$literal": "alpha"},
                        ]
                    }
                }
            ),
            started_before=now + datetime.timedelta(seconds=2),
            limit=2,
        )
    )

    assert len(filtered.attributes) == 2
    assert filtered.limit == 2
    assert filtered.offset == 0
    assert filtered.has_more is True
    filtered_counts = {
        (attr.source, attr.key): attr.span_count for attr in filtered.attributes
    }
    assert filtered_counts["custom_attrs_string", "env"] == 2
    assert filtered_counts["custom_attrs_float", "score"] == 2

    second_page = ch_server.agent_custom_attrs_schema(
        AgentCustomAttrsSchemaReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$eq": [
                            {"$getField": "agent.name"},
                            {"$literal": "alpha"},
                        ]
                    }
                }
            ),
            started_before=now + datetime.timedelta(seconds=2),
            limit=2,
            offset=2,
        )
    )
    second_page_counts = {
        (attr.source, attr.key): attr.span_count for attr in second_page.attributes
    }
    assert second_page_counts == {
        ("custom_attrs_bool", "cached"): 1,
        ("custom_attrs_string", "payload"): 1,
    }
    assert second_page.limit == 2
    assert second_page.offset == 2
    assert second_page.has_more is True

    last_page = ch_server.agent_custom_attrs_schema(
        AgentCustomAttrsSchemaReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$eq": [
                            {"$getField": "agent.name"},
                            {"$literal": "alpha"},
                        ]
                    }
                }
            ),
            started_before=now + datetime.timedelta(seconds=2),
            limit=2,
            offset=4,
        )
    )
    assert {
        (attr.source, attr.key): attr.span_count for attr in last_page.attributes
    } == {("custom_attrs_int", "retries"): 1}
    assert last_page.limit == 2
    assert last_page.offset == 4
    assert last_page.has_more is False


def test_spans_query_filters_sorts_and_projects_custom_attrs(ch_server):
    """Ungrouped spans can filter and sort by custom attrs while projecting keys."""
    project_id = _make_project_id("cattr_filter_sort")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            span_name="low",
            custom_attrs_string={"env": "prod"},
            custom_attrs_float={"score": 0.2},
            started_at=now,
        ),
        _make_span(
            project_id,
            span_name="high",
            custom_attrs_string={"env": "prod"},
            custom_attrs_float={"score": 0.9},
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            span_name="staging",
            custom_attrs_string={"env": "staging"},
            custom_attrs_float={"score": 0.5},
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$eq": [
                            {"$getField": "custom_attrs_string.env"},
                            {"$literal": "prod"},
                        ]
                    }
                }
            ),
            custom_attr_columns=[
                AgentSpanValueRef(source="custom_attrs_string", key="env"),
                AgentSpanValueRef(source="custom_attrs_float", key="score"),
            ],
            sort_by=[AgentSortBy(field="custom_attrs_float.score", direction="desc")],
        )
    )

    assert res.total_count == 2
    assert [span.span_name for span in res.spans] == ["high", "low"]
    assert [span.custom_attrs_string for span in res.spans] == [
        {"env": "prod"},
        {"env": "prod"},
    ]
    assert [span.custom_attrs_float for span in res.spans] == [
        {"score": 0.9},
        {"score": 0.2},
    ]


# ---------------------------------------------------------------------------
# Test: Agent span stats
# ---------------------------------------------------------------------------


# flaky: CI ClickHouse occasionally doesn't surface the just-inserted spans to the immediate read.
@pytest.mark.flaky(reruns=3)
def test_agent_span_stats_ungrouped_metrics(ch_server):
    """Stats API returns requested token, duration, error, and invocation metrics."""
    project_id = _make_project_id("stats")
    start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            input_tokens=100,
            output_tokens=25,
            operation_name="invoke_agent",
            status_code="OK",
            started_at=start + datetime.timedelta(seconds=10),
            ended_at=start + datetime.timedelta(seconds=10, milliseconds=100),
        ),
        _make_span(
            project_id,
            input_tokens=200,
            output_tokens=50,
            operation_name="chat",
            status_code="ERROR",
            started_at=start + datetime.timedelta(seconds=20),
            ended_at=start + datetime.timedelta(seconds=20, milliseconds=300),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=start,
            end=start + datetime.timedelta(hours=1),
            granularity=3600,
            metrics=[
                AgentSpanStatsMetricSpec(
                    alias="input_tokens",
                    value_type="number",
                    value=AgentSpanValueRef(
                        source="field",
                        key="usage.input_tokens",
                    ),
                    aggregations=["sum"],
                ),
                AgentSpanStatsMetricSpec(
                    alias="duration_ms",
                    value_type="number",
                    value=AgentSpanValueRef(source="derived", key="duration_ms"),
                    aggregations=["avg"],
                    percentiles=[95],
                ),
                AgentSpanStatsMetricSpec(
                    alias="errors",
                    value_type="boolean",
                    value=AgentSpanValueRef(source="derived", key="is_error"),
                    aggregations=["count_true"],
                ),
                AgentSpanStatsMetricSpec(
                    alias="invocations",
                    value_type="boolean",
                    value=AgentSpanValueRef(source="derived", key="is_invocation"),
                    aggregations=["count_true"],
                ),
            ],
        )
    )

    assert res.granularity == 3600
    assert len(res.rows) == 1
    row = res.rows[0]
    assert row["sum_input_tokens"] == 300
    assert row["avg_duration_ms"] == 200
    assert row["p95_duration_ms"] is not None
    assert row["count_true_errors"] == 1
    assert row["count_true_invocations"] == 1


def test_agent_span_stats_ungrouped_all_time(ch_server):
    """Ungrouped >31-day request with the whole range as one bucket returns a
    single row of all-time totals (no range-cap rejection).

    Mirrors the client recipe: start=epoch, end=now, granularity=now-epoch.
    Time buckets anchor to the epoch origin, so this is the range that
    collapses to exactly one bucket.
    """
    project_id = _make_project_id("stats-all-time")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    # Both spans predate `now` (started_at < end is exclusive) and one is far
    # past MAX_AGENT_STATS_RANGE_DAYS.
    recent = now - datetime.timedelta(minutes=1)
    old = now - datetime.timedelta(days=100)

    spans = [
        _make_span(project_id, started_at=recent),
        _make_span(project_id, started_at=old),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=epoch,
            end=now,
            granularity=int((now - epoch).total_seconds()) + 1,
            metrics=[
                AgentSpanStatsMetricSpec(
                    alias="spans",
                    value_type="datetime",
                    value=AgentSpanValueRef(source="field", key="started_at"),
                    aggregations=["count"],
                )
            ],
        )
    )

    assert len(res.rows) == 1
    assert res.rows[0]["count_spans"] == 2


def test_agent_span_stats_numeric_value_buckets(ch_server):
    """Stats API buckets the full filtered span set by numeric value range.

    A known input_tokens distribution over min=0, max=40, bins=4 pins the
    complete per-bucket output (index, edges, count) so a bounds miscompute
    fails CI rather than a dashboard.
    """
    project_id = _make_project_id("stats_hist")
    start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

    # width = (40-0)/4 = 10 -> buckets [0,10) [10,20) [20,30) [30,40].
    # counts by bucket: 0,5 -> 2 | 12,18 -> 2 | 22 -> 1 | 35,38,40 -> 3.
    token_values = [0, 5, 12, 18, 22, 35, 38, 40]
    spans = [
        _make_span(
            project_id,
            input_tokens=tokens,
            started_at=start + datetime.timedelta(seconds=idx),
            ended_at=start + datetime.timedelta(seconds=idx, milliseconds=100),
        )
        for idx, tokens in enumerate(token_values)
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=start,
            end=start + datetime.timedelta(hours=1),
            bucket_by=AgentSpanStatsNumericBucketSpec(
                type="number",
                value=AgentSpanValueRef(
                    source="field",
                    key="usage.input_tokens",
                ),
                bins=4,
            ),
            metrics=[
                AgentSpanStatsMetricSpec(
                    alias="spans",
                    value_type="boolean",
                    value=AgentSpanValueRef(source="derived", key="is_error"),
                    aggregations=["count"],
                ),
            ],
        )
    )

    assert res.bucket_type == "number"
    assert res.granularity is None
    assert [row["bucket_index"] for row in res.rows] == [0, 1, 2, 3]
    assert [row["bucket_min"] for row in res.rows] == [0, 10, 20, 30]
    assert [row["bucket_max"] for row in res.rows] == [10, 20, 30, 40]
    assert [row["count_spans"] for row in res.rows] == [2, 2, 1, 3]


@pytest.mark.flaky(reruns=3)
def test_agent_span_stats_conversation_numeric_value_buckets(ch_server):
    """Stats API can bucket grouped conversation aggregate values."""
    project_id = _make_project_id("stats_conv_hist")
    start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    conv_a = f"conv-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-{uuid.uuid4().hex[:8]}"
    conv_c = f"conv-{uuid.uuid4().hex[:8]}"

    spans = [
        _make_span(project_id, conversation_id=conv_a, started_at=start),
        _make_span(
            project_id,
            conversation_id=conv_b,
            started_at=start + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            started_at=start + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            conversation_id=conv_c,
            started_at=start + datetime.timedelta(seconds=3),
        ),
        _make_span(
            project_id,
            conversation_id=conv_c,
            started_at=start + datetime.timedelta(seconds=4),
        ),
        _make_span(
            project_id,
            conversation_id=conv_c,
            started_at=start + datetime.timedelta(seconds=5),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=start,
            end=start + datetime.timedelta(hours=1),
            bucket_by=AgentSpanStatsNumericBucketSpec(
                type="number",
                bins=2,
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measure=AgentSpanMeasureSpec(
                    alias="span_count",
                    aggregation="count",
                ),
            ),
            group_filters=[
                AgentSpanGroupFilter(
                    measure=AgentSpanMeasureSpec(
                        alias="span_count",
                        aggregation="count",
                    ),
                    min=2,
                ),
            ],
        )
    )

    assert res.bucket_type == "number"
    assert [row["count"] for row in res.rows] == [1, 1]
    assert res.rows[0]["bucket_min"] == 2
    assert res.rows[-1]["bucket_max"] == 3


def test_agent_span_stats_time_buckets_filter_conversation_aggregates(ch_server):
    """Time-bucket stats can filter to conversations matching aggregate ranges."""
    project_id = _make_project_id("stats_conv_time_filter")
    start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    conv_a = f"conv-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-{uuid.uuid4().hex[:8]}"
    conv_c = f"conv-{uuid.uuid4().hex[:8]}"

    spans = [
        _make_span(
            project_id,
            conversation_id=conv_a,
            input_tokens=5,
            output_tokens=0,
            started_at=start + datetime.timedelta(minutes=10),
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            input_tokens=10,
            output_tokens=0,
            started_at=start + datetime.timedelta(minutes=20),
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            input_tokens=20,
            output_tokens=0,
            started_at=start + datetime.timedelta(hours=1, minutes=20),
        ),
        _make_span(
            project_id,
            conversation_id=conv_c,
            input_tokens=1,
            output_tokens=0,
            started_at=start + datetime.timedelta(hours=1, minutes=30),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=start,
            end=start + datetime.timedelta(hours=2),
            granularity=3600,
            group_filters=[
                AgentSpanGroupFilter(
                    measure=AgentSpanMeasureSpec(
                        alias="total_tokens",
                        aggregation="sum",
                        value=AgentSpanValueRef(source="derived", key="total_tokens"),
                        value_type="number",
                    ),
                    min=20,
                )
            ],
            metrics=[
                AgentSpanStatsMetricSpec(
                    alias="conversations",
                    value_type="string",
                    value=AgentSpanValueRef(
                        source="field",
                        key="conversation_id",
                    ),
                    aggregations=["count_distinct"],
                ),
            ],
        )
    )

    assert res.bucket_type == "time"
    assert [row["count_distinct_conversations"] for row in res.rows] == [1, 1]


def test_agent_span_stats_buckets_custom_measure_per_conversation(ch_server):
    """Numeric stats can bucket an aggregate of custom attrs per conversation."""
    project_id = _make_project_id("stats_custom_measure_bucket")
    start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    conv_a = f"conv-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-{uuid.uuid4().hex[:8]}"
    conv_c = f"conv-{uuid.uuid4().hex[:8]}"

    spans = [
        _make_span(
            project_id,
            conversation_id=conv_a,
            custom_attrs_float={"score": 0.2},
            started_at=start,
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            custom_attrs_float={"score": 0.5},
            started_at=start + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            custom_attrs_float={"score": 0.7},
            started_at=start + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            conversation_id=conv_c,
            custom_attrs_float={"score": 0.9},
            started_at=start + datetime.timedelta(seconds=3),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=start,
            end=start + datetime.timedelta(hours=1),
            bucket_by=AgentSpanStatsNumericBucketSpec(
                type="number",
                bins=2,
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measure=AgentSpanMeasureSpec(
                    alias="avg_score",
                    aggregation="avg",
                    value=AgentSpanValueRef(
                        source="custom_attrs_float",
                        key="score",
                    ),
                    value_type="number",
                ),
            ),
            metrics=[],
        )
    )

    assert res.bucket_type == "number"
    assert [row["count"] for row in res.rows] == [1, 2]
    assert res.rows[0]["bucket_min"] == 0.2
    assert res.rows[-1]["bucket_max"] == 0.9


def test_agent_span_stats_groups_by_custom_attrs(ch_server):
    """Stats API can group chart rows by typed custom attribute map keys."""
    project_id = _make_project_id("stats_cattr")
    start = datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            custom_attrs_string={"env": "prod"},
            custom_attrs_float={"score": 0.8},
            input_tokens=100,
            output_tokens=10,
            started_at=start + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            custom_attrs_string={"env": "prod"},
            custom_attrs_float={"score": 0.6},
            input_tokens=200,
            output_tokens=20,
            started_at=start + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            custom_attrs_string={"env": "staging"},
            custom_attrs_float={"score": 0.4},
            input_tokens=50,
            output_tokens=5,
            started_at=start + datetime.timedelta(seconds=3),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_stats(
        AgentSpanStatsReq(
            project_id=project_id,
            start=start,
            end=start + datetime.timedelta(hours=1),
            granularity=3600,
            group_by=[
                AgentGroupByRef(
                    source="custom_attrs_string",
                    key="env",
                    alias="env",
                )
            ],
            metrics=[
                AgentSpanStatsMetricSpec(
                    alias="tokens",
                    value_type="number",
                    value=AgentSpanValueRef(source="derived", key="total_tokens"),
                    aggregations=["sum"],
                ),
                AgentSpanStatsMetricSpec(
                    alias="score",
                    value_type="number",
                    value=AgentSpanValueRef(
                        source="custom_attrs_float",
                        key="score",
                    ),
                    aggregations=["avg", "count"],
                ),
            ],
        )
    )

    by_env = {row["env"]: row for row in res.rows}
    assert by_env["prod"]["sum_tokens"] == 330
    assert abs(by_env["prod"]["avg_score"] - 0.7) < 1e-9
    assert by_env["prod"]["count_score"] == 2
    assert by_env["staging"]["sum_tokens"] == 55
    assert abs(by_env["staging"]["avg_score"] - 0.4) < 1e-9
    assert by_env["staging"]["count_score"] == 1


# ---------------------------------------------------------------------------
# Test: Agents MV aggregation
# ---------------------------------------------------------------------------


def test_agents_mv_aggregation(ch_server):
    """AggregatingMergeTree MV populates agents on insert."""
    project_id = _make_project_id("agents")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            agent_name="mv-agent",
            operation_name="invoke_agent",
            input_tokens=100,
            output_tokens=50,
            started_at=now,
        ),
        _make_span(
            project_id,
            agent_name="mv-agent",
            operation_name="chat",
            input_tokens=200,
            output_tokens=80,
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            agent_name="mv-agent",
            operation_name="invoke_agent",
            input_tokens=150,
            output_tokens=60,
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    assert len(res.agents) == 1

    agent = res.agents[0]
    assert agent.agent_name == "mv-agent"
    # 2 invoke_agent spans
    assert agent.invocation_count == 2
    # 3 total spans
    assert agent.span_count == 3
    assert agent.total_input_tokens == 450
    assert agent.total_output_tokens == 190


def test_agents_mv_zero_duration_when_ended_at_unset(ch_server):
    """A span inserted without ended_at (defaults to epoch) must contribute
    0 to total_duration_ms rather than wrapping via UInt64 cast to ~2^64.

    Before the fix, `toUInt64(toUnixTimestamp64Milli(ended_at) -
    toUnixTimestamp64Milli(started_at))` on an epoch ended_at produced
    18446742296979951616 and permanently poisoned the aggregate.
    """
    project_id = _make_project_id("dur_guard")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    # ended_at omitted — schema default is epoch. started_at is real.
    unset = AgentSpanCHInsertable(
        project_id=project_id,
        trace_id=uuid.uuid4().hex,
        span_id=uuid.uuid4().hex,
        span_name="unset-end",
        started_at=now,
        status_code="OK",
        operation_name="invoke_agent",
        agent_name="dur-guard-agent",
        input_tokens=10,
        output_tokens=5,
    )
    # A well-formed span that should contribute real duration to the rollup.
    finished = _make_span(
        project_id,
        agent_name="dur-guard-agent",
        operation_name="invoke_agent",
        input_tokens=20,
        output_tokens=10,
        started_at=now,
        ended_at=now + datetime.timedelta(milliseconds=150),
    )
    _insert_spans(ch_server.ch_client, [unset, finished])

    res = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    assert len(res.agents) == 1
    agent = res.agents[0]
    # Only the well-formed span contributes; unset span contributes 0.
    # The exact ms depends on clock granularity, but must be within a
    # human-reasonable range — crucially NOT the 2^64 wrap value.
    assert 0 < agent.total_duration_ms < 10_000
    # Tokens are still summed across both spans (30 + 0-token unset span had 10
    # inputs / 5 outputs).
    assert agent.total_input_tokens == 30
    assert agent.total_output_tokens == 15


# ---------------------------------------------------------------------------
# Test: Conversation chat pagination
# ---------------------------------------------------------------------------


def test_conversation_chat_paginates_turns(ch_server):
    """Conversation chat returns the latest turn page plus pagination metadata."""
    project_id = _make_project_id("conv_chat")
    conversation_id = f"conv-{uuid.uuid4().hex[:8]}"
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    trace_ids = [uuid.uuid4().hex for _ in range(3)]

    spans = []
    for i, trace_id in enumerate(trace_ids):
        started_at = now + datetime.timedelta(minutes=i)
        spans.append(
            _make_span(
                project_id,
                trace_id=trace_id,
                conversation_id=conversation_id,
                operation_name="invoke_agent",
                agent_name="chat-agent",
                input_messages=[NormalizedMessage(role="user", content=f"turn {i}")],
                started_at=started_at,
                ended_at=started_at + datetime.timedelta(seconds=1),
            )
        )
    _insert_spans(ch_server.ch_client, spans)

    first_page = ch_server.agent_conversation_chat(
        AgentConversationChatReq(
            project_id=project_id,
            conversation_id=conversation_id,
            limit=2,
        )
    )
    assert first_page.total_turns == 3
    assert first_page.has_more is True
    assert first_page.limit == 2
    assert first_page.offset == 0
    # Page zero preserves the old default: latest turns, returned
    # chronologically within the selected page.
    assert [turn.trace_id for turn in first_page.turns] == trace_ids[1:]

    second_page = ch_server.agent_conversation_chat(
        AgentConversationChatReq(
            project_id=project_id,
            conversation_id=conversation_id,
            limit=2,
            offset=2,
        )
    )
    assert second_page.total_turns == 3
    assert second_page.has_more is False
    assert second_page.limit == 2
    assert second_page.offset == 2
    assert [turn.trace_id for turn in second_page.turns] == [trace_ids[0]]


def test_conversation_chat_includes_child_spans_without_conversation_id(ch_server):
    """Conversation membership is trace-scoped after selecting conversation turns.

    Some producers attach ``conversation_id`` only to the root/invoke span. The
    chat projection still needs child LLM/tool spans in that trace, because
    those children usually carry the assistant text and tool bodies.
    """
    project_id = _make_project_id("conv_chat_children")
    conversation_id = f"conv-{uuid.uuid4().hex[:8]}"
    trace_id = uuid.uuid4().hex
    root_span_id = uuid.uuid4().hex
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=root_span_id,
            conversation_id=conversation_id,
            operation_name="invoke_agent",
            agent_name="chat-agent",
            input_messages=[NormalizedMessage(role="user", content="hello")],
            input_tokens=0,
            output_tokens=0,
            started_at=now,
            ended_at=now + datetime.timedelta(seconds=3),
        ),
        _make_span(
            project_id,
            trace_id=trace_id,
            parent_span_id=root_span_id,
            operation_name="chat",
            output_messages=[
                NormalizedMessage(role="assistant", content="hello from child")
            ],
            input_tokens=12,
            output_tokens=7,
            started_at=now + datetime.timedelta(seconds=1),
            ended_at=now + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            trace_id=trace_id,
            parent_span_id=root_span_id,
            operation_name="execute_tool",
            tool_name="lookup",
            tool_call_arguments='{"query":"hello"}',
            tool_call_result='{"ok":true}',
            input_tokens=0,
            output_tokens=0,
            started_at=now + datetime.timedelta(seconds=2),
            ended_at=now + datetime.timedelta(seconds=3),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_conversation_chat(
        AgentConversationChatReq(
            project_id=project_id,
            conversation_id=conversation_id,
        )
    )

    assert res.total_turns == 1
    assert len(res.turns) == 1
    messages = res.turns[0].messages
    assistant = next(msg for msg in messages if msg.type == "assistant_message")
    tool = next(msg for msg in messages if msg.type == "tool_call")

    assert assistant.assistant_message is not None
    assert assistant.assistant_message.text == "hello from child"
    assert assistant.assistant_message.input_tokens == 12
    assert assistant.assistant_message.output_tokens == 7
    assert tool.tool_call is not None
    assert tool.tool_call.tool_name == "lookup"
    assert tool.tool_call.tool_arguments == '{"query":"hello"}'
    assert tool.tool_call.tool_result == '{"ok":true}'


def test_conversation_chat_excludes_foreign_conversation_sharing_trace_id(ch_server):
    """A reused trace_id must not bleed foreign conversations into the chat view.

    Agent-eval workloads reuse trace_id across conversations, so the page of
    turn trace_ids matches spans from other conversations too. The chat view
    must never return another conversation's tagged spans.

    Untagged children are a known limitation: producers tag conversation_id
    only on the root span, so a foreign conversation's untagged children on a
    shared trace_id cannot be attributed and still bleed (see PR #7450).
    """
    project_id = _make_project_id("conv_chat_bleed")
    conv_a = f"conv-a-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-b-{uuid.uuid4().hex[:8]}"
    shared_trace = uuid.uuid4().hex  # reused by both conversations
    a_only_trace = uuid.uuid4().hex  # conv A's second turn, its own trace
    root_a = uuid.uuid4().hex
    root_b = uuid.uuid4().hex
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            trace_id=shared_trace,
            span_id=root_a,
            conversation_id=conv_a,
            operation_name="invoke_agent",
            input_messages=[NormalizedMessage(role="user", content="userA-shared")],
            started_at=now,
            ended_at=now + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            trace_id=shared_trace,
            parent_span_id=root_a,
            operation_name="chat",
            output_messages=[
                NormalizedMessage(role="assistant", content="childA-text")
            ],
            started_at=now + datetime.timedelta(seconds=1),
            ended_at=now + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            trace_id=shared_trace,
            span_id=root_b,
            conversation_id=conv_b,
            operation_name="invoke_agent",
            input_messages=[NormalizedMessage(role="user", content="userB-foreign")],
            output_messages=[
                NormalizedMessage(role="assistant", content="assistantB-foreign")
            ],
            started_at=now + datetime.timedelta(seconds=1),
            ended_at=now + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            trace_id=shared_trace,
            parent_span_id=root_b,
            operation_name="chat",
            output_messages=[
                NormalizedMessage(role="assistant", content="childB-foreign")
            ],
            started_at=now + datetime.timedelta(seconds=1),
            ended_at=now + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            trace_id=a_only_trace,
            conversation_id=conv_a,
            operation_name="invoke_agent",
            input_messages=[NormalizedMessage(role="user", content="userA-only")],
            started_at=now + datetime.timedelta(minutes=1),
            ended_at=now + datetime.timedelta(minutes=1, seconds=1),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_conversation_chat(
        AgentConversationChatReq(project_id=project_id, conversation_id=conv_a)
    )

    assert res.total_turns == 2
    assert {turn.trace_id for turn in res.turns} == {shared_trace, a_only_trace}

    texts = [
        payload.text
        for turn in res.turns
        for msg in turn.messages
        for payload in (msg.user_message, msg.assistant_message)
        if payload is not None
    ]
    assert "userA-shared" in texts
    assert "childA-text" in texts
    assert "userA-only" in texts
    # conv B's tagged root is excluded by conversation_id scoping.
    assert "userB-foreign" not in texts
    assert "assistantB-foreign" not in texts
    # Known limitation (PR #7450 discussion): conv B's untagged child shares
    # the trace_id, so it currently bleeds. Flip to `not in` when fixed.
    assert "childB-foreign" in texts


# ---------------------------------------------------------------------------
# Test: Message search
# ---------------------------------------------------------------------------


def test_message_search(ch_server):
    """End-to-end search against the `messages` table.

    Spans are inserted and the ClickHouse MV populates the search index
    automatically; no Python-side extraction runs. Verifies that content
    LIKE + span-level filters return the expected hits.
    """
    project_id = _make_project_id("search")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            conversation_id="search-conv-1",
            conversation_name="Search Test",
            output_messages=[
                NormalizedMessage(
                    role="assistant",
                    content="The quantum entanglement hypothesis is fascinating.",
                ),
            ],
            started_at=now,
        ),
        _make_span(
            project_id,
            conversation_id="search-conv-1",
            conversation_name="Search Test",
            output_messages=[
                NormalizedMessage(
                    role="assistant",
                    content="Classical mechanics still has many applications.",
                ),
            ],
            started_at=now + datetime.timedelta(seconds=1),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # Search for "quantum" — should match 1 message
    res = ch_server.agent_search(AgentSearchReq(project_id=project_id, query="quantum"))
    assert len(res.results) >= 1
    matched = res.results[0]
    assert "quantum" in matched.matched_messages[0].content_preview.lower()

    # Search for "xyznonexistent" — should match nothing
    res_empty = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="xyznonexistent")
    )
    assert res_empty.results == []


def test_message_search_shared_digest_across_spans(ch_server):
    """Two spans carrying identical output message content should produce
    two rows in `messages` that share a single content_digest — enabling
    read-side dedup via GROUP BY content_digest when desired.
    """
    project_id = _make_project_id("search_dedup")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    repeated = "Identical assistant response across two different spans."
    spans = [
        _make_span(
            project_id,
            conversation_id="dedup-conv-1",
            output_messages=[NormalizedMessage(role="assistant", content=repeated)],
            started_at=now,
        ),
        _make_span(
            project_id,
            conversation_id="dedup-conv-2",
            output_messages=[NormalizedMessage(role="assistant", content=repeated)],
            started_at=now + datetime.timedelta(seconds=1),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="Identical assistant")
    )
    # One row per occurrence across two conversations
    total_matches = sum(len(r.matched_messages) for r in res.results)
    assert total_matches == 2
    # Both occurrences share a single content_digest
    digests = {m.content_digest for r in res.results for m in r.matched_messages}
    assert len(digests) == 1


def test_message_search_trace_id_full_content(ch_server):
    """Structured retrieval: empty query + trace_id + full_content returns the
    trace's user/assistant/system messages untruncated, excluding tool roles.
    This is the path the agent scoring fallback uses.
    """
    project_id = _make_project_id("search_trace_full")
    trace_id = uuid.uuid4().hex
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    long_text = "x" * 600  # exceeds the 500-char preview cap

    spans = [
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=uuid.uuid4().hex,
            operation_name="chat",
            started_at=now,
            system_instructions=["be helpful"],
            input_messages=[NormalizedMessage(role="user", content=long_text)],
            output_messages=[NormalizedMessage(role="assistant", content="hi")],
        ),
        # A tool span in the same trace — its tool_result row must be filtered out.
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=uuid.uuid4().hex,
            operation_name="execute_tool",
            started_at=now + datetime.timedelta(seconds=1),
            tool_call_result="tool output",
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_search(
        AgentSearchReq(
            project_id=project_id,
            query="",
            trace_id=trace_id,
            roles=["user", "assistant", "system"],
            truncate_content=False,
        )
    )
    by_role: dict[str, list[str]] = {}
    for r in res.results:
        for m in r.matched_messages:
            by_role.setdefault(m.role, []).append(m.content_preview)

    assert by_role["user"] == [long_text]  # full content, not the 500-char preview
    assert by_role["assistant"] == ["hi"]
    assert by_role["system"] == ["be helpful"]
    assert "tool_result" not in by_role  # excluded by the roles filter


def test_message_search_indexes_tool_calls(ch_server):
    """tool_call_arguments and tool_call_result should each produce a
    searchable occurrence with role 'tool_call' / 'tool_result'.
    """
    project_id = _make_project_id("search_tools")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            conversation_id="tool-conv-1",
            operation_name="execute_tool",
            tool_call_arguments='{"city":"Reykjavík"}',
            tool_call_result='{"temperature":5,"condition":"snowy"}',
            started_at=now,
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # Hit on the arguments side
    res_args = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="Reykjavík")
    )
    assert len(res_args.results) == 1
    assert res_args.results[0].matched_messages[0].role == "tool_call"

    # Hit on the result side
    res_result = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="snowy")
    )
    assert len(res_result.results) == 1
    assert res_result.results[0].matched_messages[0].role == "tool_result"

    # UI/back-compat alias: "tool" should include both persisted tool roles.
    res_tool_alias = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="Reykjavík", roles=["tool"])
    )
    assert len(res_tool_alias.results) == 1
    assert res_tool_alias.results[0].matched_messages[0].role == "tool_call"


# ---------------------------------------------------------------------------
# Test: Query DSL end-to-end
# ---------------------------------------------------------------------------


def test_query_dsl_combines_semconv_column_and_custom_attr(ch_server):
    """Compile and execute a Mongo-style query mixing a semconv-mapped column
    and an unprefixed custom_attrs_string key dispatched via sibling-literal type.
    """
    project_id = _make_project_id("dsl")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        # alpha / prod — matches
        _make_span(
            project_id,
            agent_name="alpha",
            custom_attrs_string={"env": "prod"},
            started_at=now,
        ),
        # alpha / staging — agent matches but env doesn't
        _make_span(
            project_id,
            agent_name="alpha",
            custom_attrs_string={"env": "staging"},
            started_at=now + datetime.timedelta(seconds=1),
        ),
        # beta / prod — env matches but agent doesn't
        _make_span(
            project_id,
            agent_name="beta",
            custom_attrs_string={"env": "prod"},
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    q = Query.model_validate(
        {
            "$expr": {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "agent.name"},
                            {"$literal": "alpha"},
                        ]
                    },
                    # `env` is unknown -> falls through to custom_attrs_string
                    # (sibling literal is a str, so the String map).
                    {"$eq": [{"$getField": "env"}, {"$literal": "prod"}]},
                ]
            }
        }
    )
    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, query=q)
    )
    assert res.total_count == 1
    assert len(res.spans) == 1
    assert res.spans[0].agent_name == "alpha"


def test_query_dsl_typed_custom_attr_comparison(ch_server):
    """Int-typed custom attributes route to `custom_attrs_int` via the
    sibling-literal type and compare numerically.
    """
    project_id = _make_project_id("dsl_int")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        # retries=5 — matches > 3
        _make_span(
            project_id,
            custom_attrs_int={"retries": 5},
            started_at=now,
        ),
        # retries=1 — doesn't match
        _make_span(
            project_id,
            custom_attrs_int={"retries": 1},
            started_at=now + datetime.timedelta(seconds=1),
        ),
        # no retries attr — doesn't match
        _make_span(
            project_id,
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    q = Query.model_validate(
        {"$expr": {"$gt": [{"$getField": "retries"}, {"$literal": 3}]}}
    )
    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, query=q)
    )
    assert res.total_count == 1
    assert len(res.spans) == 1


# ---------------------------------------------------------------------------
# Test: end-to-end base64 -> Content-ref conversion on the GenAI OTel agents
# ingest path (mirrors test_calls_complete's data-URI conversion test, but for
# the agents endpoint).
# ---------------------------------------------------------------------------


def _ref_safe_external_project_id(prefix: str) -> str:
    """A unique EXTERNAL ``entity/project`` id whose internal form carries no '/'.

    A real client submits an external ``entity/project`` id; the adapter maps it
    to the internal id via ``base64(entity/project)`` and embeds that internal id
    in ``weave-trace-internal:///<internal>/object/...`` refs. ``InternalObjectRef``
    rejects a project_id containing '/', and standard base64 can emit '/', so
    regenerate the external id until its base64 form is clean.
    """
    while True:
        external = f"test/{prefix}_{uuid.uuid4().hex[:8]}"
        internal = base64.b64encode(external.encode("ascii")).decode("ascii")
        if "/" not in internal:
            return external


def _build_genai_chat_processed_span(
    trace_id: bytes,
    span_id: bytes,
    input_messages_json: str,
) -> tsi.ProcessedResourceSpans:
    """Build a real OTel proto ``chat`` span carrying JSON-encoded input messages.

    The messages arrive under ``gen_ai.input.messages`` as a JSON *string* — the
    shape that exercises the ``_strip_message_attr`` -> ``replace_base64_in_raw_messages``
    message-payload pass on ingest.
    """
    span = Span()
    span.name = "chat gemini-2.0-flash"
    span.trace_id = trace_id
    span.span_id = span_id
    now_ns = int(datetime.datetime.now().timestamp() * 1_000_000_000)
    span.start_time_unix_nano = now_ns
    span.end_time_unix_nano = now_ns + 1_000_000_000
    span.kind = 1  # CLIENT

    op_kv = KeyValue()
    op_kv.key = "gen_ai.operation.name"
    op_kv.value.string_value = "chat"
    span.attributes.append(op_kv)

    model_kv = KeyValue()
    model_kv.key = "gen_ai.request.model"
    model_kv.value.string_value = "gemini-2.0-flash"
    span.attributes.append(model_kv)

    msgs_kv = KeyValue()
    msgs_kv.key = "gen_ai.input.messages"
    msgs_kv.value.string_value = input_messages_json
    span.attributes.append(msgs_kv)

    span.status.code = StatusCode.OK.value  # type: ignore[assignment]

    scope = InstrumentationScope()
    scope.name = "test_instrumentation"
    scope.version = "1.0.0"
    scope_spans = ScopeSpans()
    scope_spans.scope.CopyFrom(scope)
    scope_spans.spans.append(span)

    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(Resource())
    resource_spans.scope_spans.append(scope_spans)

    return tsi.ProcessedResourceSpans(
        entity="test-entity",
        project="test-project",
        run_id=None,
        resource_spans=resource_spans,
    )


# flaky: CI ClickHouse occasionally doesn't surface the just-inserted spans to
# the immediate read.
@pytest.mark.flaky(reruns=3)
def test_genai_otel_export_ref_boundary_internal_in_db_external_out(
    ch_server, trace_server
):
    """End-to-end ref-boundary check for the GenAI OTel agents ingest/read path.

    A real client submits ONE Gemini-style ``chat`` span through the EXTERNAL
    adapter (external ``entity/project`` id, external user id, external refs).
    Its ``gen_ai.input.messages`` JSON carries three parts: a text part, an image
    part with an inline base64 data-URI (the server converts it to a stored
    Content ref), and a ``resource`` part embedding an EXTERNAL weave ref (an
    MCP-fetched dataset). The invariant is then asserted in BOTH directions:

      * DB truth (raw internal server): the stored message content holds ONLY
        internal refs — the base64 became an internal Content ref, and the
        external dataset ref was converted to internal on ingest; no external
        scheme and no base64 blob survive.
      * External read (through the adapter): the same content holds ONLY
        external refs — ``weave-trace-internal://`` never leaks (the leak the
        boundary converter closes), and the dataset ref round-trips
        ext -> int -> ext unchanged.

    Also checks the chat view surfaces the media consistently (internal refs on
    the raw server, external refs through the adapter) and that the converted
    Content object is attributed to the caller's ``wb_user_id``.
    """
    external_project_id = _ref_safe_external_project_id("genai_otel_boundary")
    internal_project_id = base64.b64encode(external_project_id.encode("ascii")).decode(
        "ascii"
    )
    # The client sends an external user id; the adapter converts it to the
    # internal (base64) form the internal server persists on the Content object.
    external_user_id = "user-42"
    internal_user_id = base64.b64encode(external_user_id.encode("ascii")).decode(
        "ascii"
    )

    raw_bytes = b"a" * (AUTO_CONVERSION_MIN_SIZE + 10)
    b64_data = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:image/png;base64,{b64_data}"
    # An MCP-fetched dataset ref, in the same external project as the span so it
    # maps back cleanly on read.
    external_dataset_ref = f"weave:///{external_project_id}/object/mcp_dataset:v1"
    internal_dataset_ref = (
        f"weave-trace-internal:///{internal_project_id}/object/mcp_dataset:v1"
    )

    trace_id = uuid.uuid4().bytes
    span_id = uuid.uuid4().bytes[:8]
    input_messages_json = json.dumps(
        [
            {
                "role": "user",
                "parts": [
                    {"type": "text", "content": "describe"},
                    {"type": "image", "url": data_uri},
                    {"type": "resource", "ref": external_dataset_ref},
                ],
            }
        ]
    )
    processed = _build_genai_chat_processed_span(trace_id, span_id, input_messages_json)

    # Submit through the EXTERNAL adapter, exactly as a real client would: no
    # internal ids or internal refs cross this boundary.
    res = trace_server.genai_otel_export(
        GenAIOTelExportReq(
            processed_spans=[processed],
            project_id=external_project_id,
            wb_user_id=external_user_id,
        )
    )
    assert res.accepted_spans == 1
    assert res.rejected_spans == 0
    assert res.error_message == ""

    # --- DB TRUTH (raw internal server): only internal refs, no base64 ---
    stored = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=internal_project_id, include_details=True)
    )
    assert len(stored.spans) == 1
    stored_span = stored.spans[0]
    assert stored_span.operation_name == "chat"
    assert len(stored_span.input_messages) == 1

    stored_content = stored_span.input_messages[0].content
    stored_parts = json.loads(stored_content)

    # Text part verbatim; the base64 image url is now a compact internal Content
    # ref; the external dataset ref was rewritten to internal on ingest.
    internal_image_ref = stored_parts[1]["url"]
    assert stored_parts == [
        {"type": "text", "content": "describe"},
        {"type": "image", "url": internal_image_ref},
        {"type": "resource", "ref": internal_dataset_ref},
    ]

    parsed_image_ref = ri.parse_internal_uri(internal_image_ref)
    assert isinstance(parsed_image_ref, ri.InternalObjectRef)
    assert parsed_image_ref.project_id == internal_project_id
    assert (
        internal_image_ref == f"weave-trace-internal:///{internal_project_id}/object/"
        f"{parsed_image_ref.name}:{parsed_image_ref.version}"
    )

    # No base64 blob and no external scheme survive anywhere in the stored content.
    assert b64_data not in stored_content
    assert "weave:///" not in stored_content

    # --- EXTERNAL READ (through the adapter): only external refs, no leak ---
    external = trace_server.agent_spans_query(
        AgentSpansQueryReq(project_id=external_project_id, include_details=True)
    )
    assert len(external.spans) == 1
    external_span = external.spans[0]
    assert external_span.project_id == external_project_id
    external_content = external_span.input_messages[0].content
    external_parts = json.loads(external_content)

    expected_external_image_ref = (
        f"weave:///{external_project_id}/object/"
        f"{parsed_image_ref.name}:{parsed_image_ref.version}"
    )
    assert external_parts == [
        {"type": "text", "content": "describe"},
        {"type": "image", "url": expected_external_image_ref},
        {"type": "resource", "ref": external_dataset_ref},
    ]
    # KEY leak assertion: the internal scheme must never reach the client.
    assert "weave-trace-internal:///" not in external_content
    # The embedded dataset ref round-trips ext -> int -> ext unchanged.
    assert external_parts[2]["ref"] == external_dataset_ref

    trace_id_hex = stored_span.trace_id

    # --- Chat view (raw internal server): media surfaces as internal refs ---
    internal_chat = ch_server.agent_traces_chat(
        AgentTraceChatReq(project_id=internal_project_id, trace_id=trace_id_hex)
    )
    internal_user_messages = [
        m for m in internal_chat.messages if m.type == "user_message"
    ]
    assert len(internal_user_messages) == 1
    assert internal_user_messages[0].user_message.content_refs == [
        internal_image_ref,
        internal_dataset_ref,
    ]

    # --- Chat view (external adapter read path): int refs -> external weave:// ---
    external_chat = trace_server.agent_traces_chat(
        AgentTraceChatReq(project_id=external_project_id, trace_id=trace_id_hex)
    )
    external_user_messages = [
        m for m in external_chat.messages if m.type == "user_message"
    ]
    assert len(external_user_messages) == 1
    assert external_user_messages[0].user_message.content_refs == [
        expected_external_image_ref,
        external_dataset_ref,
    ]

    # --- The converted Content object is attributed to the caller ---
    obj = ch_server.obj_read(
        tsi.ObjReadReq(
            project_id=internal_project_id,
            object_id=parsed_image_ref.name,
            digest=parsed_image_ref.version,
        )
    )
    assert obj.obj.wb_user_id == internal_user_id


# ---------------------------------------------------------------------------
# Tests: agent target IDs persisted on feedback create
# ---------------------------------------------------------------------------


def test_feedback_create_derives_conversation_target_id_from_ref(ch_server):
    """Conversation-targeted agent feedback derives the denormalized ID."""
    project_id = _make_project_id("fb-conv-id-derived")
    conv_id = f"conv-{uuid.uuid4().hex[:8]}"
    conv_ref = ri.InternalAgentConversationRef(
        project_id=project_id, conversation_id=conv_id
    ).uri

    ch_server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=conv_ref,
            feedback_type=AGENT_USER_FEEDBACK_TYPE,
            payload={},
            scorer_tags=["hallucination"],
            wb_user_id="u1",
        )
    )

    res = ch_server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            fields=["span_conversation_id", "span_trace_id", "scorer_tags"],
        )
    )
    assert res.result == [
        {
            "span_conversation_id": conv_id,
            "span_trace_id": "",
            "scorer_tags": ["hallucination"],
        }
    ]


def test_feedback_create_derives_turn_target_id_from_ref(ch_server):
    """Turn-targeted agent feedback derives the denormalized trace ID."""
    project_id = _make_project_id("fb-turn-id-derived")
    trace_id = uuid.uuid4().hex
    turn_ref = ri.InternalAgentTurnRef(project_id=project_id, trace_id=trace_id).uri

    ch_server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=turn_ref,
            feedback_type=AGENT_USER_FEEDBACK_TYPE,
            payload={},
            scorer_tags=["needs-review"],
            wb_user_id="u1",
        )
    )

    res = ch_server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            fields=["span_conversation_id", "span_trace_id", "scorer_tags"],
        )
    )
    assert res.result == [
        {
            "span_conversation_id": "",
            "span_trace_id": trace_id,
            "scorer_tags": ["needs-review"],
        }
    ]


def test_feedback_create_persists_supplied_conversation_target_id(ch_server):
    """Conversation-targeted feedback persists the supplied denormalized ID."""
    project_id = _make_project_id("fb-conv-id")
    conv_id = f"conv-{uuid.uuid4().hex[:8]}"
    conv_ref = ri.InternalAgentConversationRef(
        project_id=project_id, conversation_id=conv_id
    ).uri

    ch_server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=conv_ref,
            feedback_type=AGENT_USER_FEEDBACK_TYPE,
            payload={},
            scorer_tags=["hallucination"],
            span_conversation_id=conv_id,
            wb_user_id="u1",
        )
    )

    res = ch_server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            fields=["span_conversation_id", "span_trace_id", "scorer_tags"],
        )
    )
    assert res.result == [
        {
            "span_conversation_id": conv_id,
            "span_trace_id": "",
            "scorer_tags": ["hallucination"],
        }
    ]


def test_feedback_create_persists_supplied_span_target_ids(ch_server):
    """Span-targeted feedback persists supplied denormalized IDs."""
    project_id = _make_project_id("fb-span-id")
    conv_id = f"conv-{uuid.uuid4().hex[:8]}"
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex
    span_ref = ri.InternalAgentSpanRef(project_id=project_id, span_id=span_id).uri

    ch_server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=span_ref,
            feedback_type=AGENT_USER_FEEDBACK_TYPE,
            payload={},
            scorer_tags=["needs-review"],
            span_conversation_id=conv_id,
            span_trace_id=trace_id,
            wb_user_id="u3",
        )
    )

    res = ch_server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            fields=["span_conversation_id", "span_trace_id", "scorer_tags"],
        )
    )
    assert res.result == [
        {
            "span_conversation_id": conv_id,
            "span_trace_id": trace_id,
            "scorer_tags": ["needs-review"],
        }
    ]


def test_feedback_create_batch_persists_supplied_agent_target_ids(ch_server):
    project_id = _make_project_id("fb-batch-target-ids")
    conv_ref_id = f"conv-{uuid.uuid4().hex[:8]}"
    turn_conv_id = f"conv-{uuid.uuid4().hex[:8]}"
    span_conv_id = f"conv-{uuid.uuid4().hex[:8]}"
    turn_trace_id = uuid.uuid4().hex
    span_trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex
    conv_ref = ri.InternalAgentConversationRef(
        project_id=project_id, conversation_id=conv_ref_id
    ).uri
    turn_ref = ri.InternalAgentTurnRef(
        project_id=project_id, trace_id=turn_trace_id
    ).uri
    span_ref = ri.InternalAgentSpanRef(project_id=project_id, span_id=span_id).uri

    ch_server.feedback_create_batch(
        tsi.FeedbackCreateBatchReq(
            batch=[
                tsi.FeedbackCreateReq(
                    project_id=project_id,
                    weave_ref=conv_ref,
                    feedback_type=AGENT_USER_FEEDBACK_TYPE,
                    payload={},
                    scorer_tags=["conv-tag"],
                    span_conversation_id=conv_ref_id,
                    wb_user_id="u1",
                ),
                tsi.FeedbackCreateReq(
                    project_id=project_id,
                    weave_ref=turn_ref,
                    feedback_type=AGENT_USER_FEEDBACK_TYPE,
                    payload={},
                    scorer_tags=["turn-tag"],
                    span_conversation_id=turn_conv_id,
                    span_trace_id=turn_trace_id,
                    wb_user_id="u2",
                ),
                tsi.FeedbackCreateReq(
                    project_id=project_id,
                    weave_ref=span_ref,
                    feedback_type=AGENT_USER_FEEDBACK_TYPE,
                    payload={},
                    scorer_tags=["span-tag"],
                    span_conversation_id=span_conv_id,
                    span_trace_id=span_trace_id,
                    wb_user_id="u3",
                ),
            ]
        )
    )

    res = ch_server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            fields=[
                "weave_ref",
                "span_conversation_id",
                "span_trace_id",
                "scorer_tags",
            ],
        )
    )
    actual = sorted(res.result, key=lambda row: row["weave_ref"])
    expected = sorted(
        [
            {
                "weave_ref": conv_ref,
                "span_conversation_id": conv_ref_id,
                "span_trace_id": "",
                "scorer_tags": ["conv-tag"],
            },
            {
                "weave_ref": turn_ref,
                "span_conversation_id": turn_conv_id,
                "span_trace_id": turn_trace_id,
                "scorer_tags": ["turn-tag"],
            },
            {
                "weave_ref": span_ref,
                "span_conversation_id": span_conv_id,
                "span_trace_id": span_trace_id,
                "scorer_tags": ["span-tag"],
            },
        ],
        key=lambda row: row["weave_ref"],
    )
    assert actual == expected


def test_feedback_create_rejects_trace_id_for_conversation_ref(ch_server):
    project_id = _make_project_id("fb-conv-ref-trace-id")
    conv_ref = ri.InternalAgentConversationRef(
        project_id=project_id, conversation_id="conv-a"
    ).uri

    with pytest.raises(
        InvalidRequest,
        match="feedback span_trace_id 'trace-a' cannot be supplied for "
        "conversation-targeted feedback",
    ):
        ch_server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=conv_ref,
                feedback_type=AGENT_USER_FEEDBACK_TYPE,
                payload={},
                scorer_tags=["hallucination"],
                span_trace_id="trace-a",
                wb_user_id="u1",
            )
        )


def test_feedback_create_batch_rejects_conflicting_agent_target_ids(ch_server):
    project_id = _make_project_id("fb-batch-target-id-conflict")
    conv_ref = ri.InternalAgentConversationRef(
        project_id=project_id, conversation_id="conv-a"
    ).uri
    turn_ref = ri.InternalAgentTurnRef(project_id=project_id, trace_id="trace-a").uri

    with pytest.raises(
        InvalidRequest,
        match="feedback span_conversation_id 'conv-b' conflicts with "
        "conversation ref 'conv-a'",
    ):
        ch_server.feedback_create_batch(
            tsi.FeedbackCreateBatchReq(
                batch=[
                    tsi.FeedbackCreateReq(
                        project_id=project_id,
                        weave_ref=conv_ref,
                        feedback_type=AGENT_USER_FEEDBACK_TYPE,
                        payload={},
                        scorer_tags=["conv-tag"],
                        span_conversation_id="conv-b",
                        wb_user_id="u1",
                    )
                ]
            )
        )

    with pytest.raises(
        InvalidRequest,
        match="feedback span_trace_id 'trace-b' conflicts with turn ref 'trace-a'",
    ):
        ch_server.feedback_create_batch(
            tsi.FeedbackCreateBatchReq(
                batch=[
                    tsi.FeedbackCreateReq(
                        project_id=project_id,
                        weave_ref=turn_ref,
                        feedback_type=AGENT_USER_FEEDBACK_TYPE,
                        payload={},
                        scorer_tags=["turn-tag"],
                        span_trace_id="trace-b",
                        wb_user_id="u2",
                    )
                ]
            )
        )


# ---------------------------------------------------------------------------
# Test: signal filtering on agent conversations (Task 7)
# ---------------------------------------------------------------------------


# flaky: CI ClickHouse occasionally doesn't surface the just-inserted spans to the immediate read.
@pytest.mark.flaky(reruns=3)
def test_filter_conversations_by_signal(ch_server):
    """E2E proof of signal filter union semantics and mutation-correctness.

    Seeds two conversations (conv-A, conv-B). Tags a turn in conv-A and a
    conversation-level tag in conv-B. Verifies:
    - Tag filter returns only the tagged conversation.
    - Rating filter returns only the rated conversation.
    - No filter returns both.
    - Conv-level tag matches the other union arm.
    - total_count reflects the filter (not the unfiltered conversation count).
    - A combined tag + rating filter matches across feedback rows (human tag and
      monitor rating live on different rows) and AND-s the two grains.
    - Purging the feedback removes it from the filter result.
    """
    project_id = _make_project_id("signal-filter")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    trace_a = uuid.uuid4().hex
    trace_b = uuid.uuid4().hex
    conv_a = f"conv-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-{uuid.uuid4().hex[:8]}"

    # Seed one span per conversation so each appears in grouped query results.
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id,
                trace_id=trace_a,
                conversation_id=conv_a,
                operation_name="invoke_agent",
                started_at=now,
            ),
            _make_span(
                project_id,
                trace_id=trace_b,
                conversation_id=conv_b,
                operation_name="invoke_agent",
                started_at=now + datetime.timedelta(seconds=1),
            ),
        ],
    )

    # Helper: run grouped query and return sorted conversation_ids.
    def filtered_ids(signal_filters: AgentSignalFilter | None) -> list[str]:
        res = ch_server.agent_spans_query(
            AgentSpansQueryReq(
                project_id=project_id,
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                signal_filters=signal_filters,
            )
        )
        return sorted(
            g.group_keys["conversation_id"]
            for g in res.groups
            if g.group_keys.get("conversation_id") in {conv_a, conv_b}
        )

    def filtered_count(signal_filters: AgentSignalFilter | None) -> int:
        return ch_server.agent_spans_query(
            AgentSpansQueryReq(
                project_id=project_id,
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                signal_filters=signal_filters,
            )
        ).total_count

    # Baseline: no signal filter returns both conversations, and total_count agrees.
    assert filtered_ids(None) == sorted([conv_a, conv_b])
    assert filtered_count(None) == 2

    # Tag a TURN in conv-A. The producer (here, the monitor) supplies
    # span_conversation_id from the scored span, so the turn-level signal resolves
    # up to conv-A.
    turn_a_ref = ri.InternalAgentTurnRef(project_id=project_id, trace_id=trace_a).uri
    fb_a = ch_server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=turn_a_ref,
            feedback_type=AGENT_MONITOR_FEEDBACK_TYPE,
            payload={},
            wb_user_id="u1",
            runnable_ref=ri.InternalOpRef(
                project_id=project_id, name="scorer", version="v1"
            ).uri,
            call_ref=ri.InternalCallRef(project_id=project_id, id=trace_a).uri,
            trigger_ref=ri.InternalObjectRef(
                project_id=project_id, name="monitor", version="v1"
            ).uri,
            scorer_tags=["flagged"],
            scorer_ratings={"_rating_": 0.9},
            span_conversation_id=conv_a,
            span_trace_id=trace_a,
        )
    )

    # Tag filter selects only conv-A (turn-level signal resolves up to conversation).
    assert filtered_ids(AgentSignalFilter(tags=["flagged"])) == [conv_a]
    # total_count applies the filter too (else the UI paginates over phantom empties).
    assert filtered_count(AgentSignalFilter(tags=["flagged"])) == 1

    # Rating filter selects conv-A (0.9 >= 0.8).
    assert filtered_ids(
        AgentSignalFilter(
            ratings=[RatingCondition(scorer_key="_rating_", op="gte", value=0.8)]
        )
    ) == [conv_a]

    # Arm 2 of the union: conversation-level tag on conv-B.
    conv_b_ref = ri.InternalAgentConversationRef(
        project_id=project_id, conversation_id=conv_b
    ).uri
    ch_server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=conv_b_ref,
            feedback_type=AGENT_USER_FEEDBACK_TYPE,
            payload={},
            wb_user_id="u2",
            scorer_tags=["reviewed"],
        )
    )
    assert filtered_ids(AgentSignalFilter(tags=["reviewed"])) == [conv_b]

    # Combined tag + rating must match ACROSS rows: add a human tag on conv-A on a
    # separate wandb.agent_user_feedback row from the monitor's rating. A single-row
    # conjunction would miss this; the per-grain sub-selects match it.
    ch_server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=turn_a_ref,
            feedback_type=AGENT_USER_FEEDBACK_TYPE,
            payload={},
            wb_user_id="u3",
            scorer_tags=["human-flag"],
            span_conversation_id=conv_a,
            span_trace_id=trace_a,
        )
    )
    combined = AgentSignalFilter(
        tags=["human-flag"],
        ratings=[RatingCondition(scorer_key="_rating_", op="gte", value=0.8)],
    )
    assert filtered_ids(combined) == [conv_a]

    # AND across grains: conv-B has the "reviewed" tag but no rating, so a combined
    # tag + rating filter excludes it.
    assert (
        filtered_ids(
            AgentSignalFilter(
                tags=["reviewed"],
                ratings=[RatingCondition(scorer_key="_rating_", op="gte", value=0.8)],
            )
        )
        == []
    )

    # Mutation-correctness: purge the conv-A turn feedback; tag filter returns [].
    ch_server.feedback_purge(
        tsi.FeedbackPurgeReq(
            project_id=project_id,
            query=Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "id"},
                            {"$literal": fb_a.id},
                        ]
                    }
                }
            ),
        )
    )
    assert filtered_ids(AgentSignalFilter(tags=["flagged"])) == []
