"""Single-span filtering preserves trace attribution and project isolation."""

import base64
import datetime

import pytest

from tests.trace_server.helpers import make_project_id
from tests.trace_server.test_genai_agent_queries import _insert_spans, _make_span
from weave.trace_server.agents.types import AgentGroupByRef, AgentSpansQueryReq
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.interface.query import Query

NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


@pytest.fixture
def lookup_project(ch_server: ClickHouseTraceServer) -> str:
    project_id = make_project_id("lookup")
    other_project = make_project_id("other_lookup")
    other_entity = base64.b64encode(b"other/lookup").decode()
    spans = [
        _make_span(
            project_id,
            trace_id="turn",
            span_id="root",
            agent_name="Planner",
            agent_version="v1",
            agent_id="planner",
            conversation_id="chat",
            started_at=NOW - datetime.timedelta(minutes=5),
        ),
        _make_span(
            project_id,
            trace_id="turn",
            span_id="child",
            agent_name="",
            started_at=NOW,
            custom_attrs_string={"stage": "answer"},
        ),
        _make_span(
            project_id,
            trace_id="turn",
            span_id="own",
            agent_name="Writer",
            agent_version="",
            agent_id="writer",
            started_at=NOW,
        ),
        _make_span(
            project_id,
            trace_id="unrelated",
            span_id="other",
            agent_name="Other",
            started_at=NOW,
        ),
        _make_span(
            project_id,
            trace_id="unrelated",
            span_id="other_child",
            agent_name="",
            started_at=NOW + datetime.timedelta(seconds=1),
        ),
        _make_span(
            other_project,
            trace_id="turn",
            span_id="child",
            agent_name="Foreign",
            started_at=NOW - datetime.timedelta(minutes=10),
        ),
        _make_span(
            other_entity,
            trace_id="turn",
            span_id="child",
            agent_name="Foreign",
            started_at=NOW - datetime.timedelta(minutes=15),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    return project_id


@pytest.mark.parametrize(
    ("span_id", "agent", "expected"),
    [
        ("child", "Planner", ("Planner", "v1", "planner", "chat")),
        ("own", "Writer", ("Writer", "", "writer", "chat")),
        ("child", "Foreign", None),
        ("child", "Other", None),
        ("missing", "Planner", None),
        ("child' OR 1=1 --", "Planner", None),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_lookup_identity_and_isolation(
    ch_server: ClickHouseTraceServer,
    lookup_project: str,
    span_id: str,
    agent: str,
    expected: tuple[str, str, str, str] | None,
    reverse: bool,
) -> None:
    operands = [{"$getField": "span_id"}, {"$literal": span_id}]
    if reverse:
        operands.reverse()

    expr = {
        "$and": [
            {
                "$and": [
                    {"$eq": operands},
                    {"$eq": [{"$getField": "agent.name"}, {"$literal": agent}]},
                ]
            },
        ]
    }
    req = AgentSpansQueryReq(
        project_id=lookup_project,
        query=Query.model_validate({"$expr": expr}),
        started_after=NOW,
        started_before=NOW + datetime.timedelta(minutes=1),
        include_details=True,
        include_costs=True,
        limit=1,
    )
    actual = ch_server.agent_spans_query(req)
    # The equivalent OR keeps the unscoped attribution path as a reference.
    reference_query = Query.model_validate({"$expr": {"$or": [expr, expr]}})
    reference = ch_server.agent_spans_query(
        req.model_copy(update={"query": reference_query})
    )
    assert actual == reference
    assert actual.total_count == (0 if expected is None else 1)
    assert [
        (s.agent_name, s.agent_version, s.agent_id, s.conversation_id)
        for s in actual.spans
    ] == ([] if expected is None else [expected])

    page = ch_server.agent_spans_query(req.model_copy(update={"offset": 1}))
    assert page.total_count == actual.total_count
    assert page.spans == []


@pytest.mark.parametrize(
    ("operator", "expected_ids"),
    [
        ("$or", {"child", "root", "other", "other_child"}),
        ("$not", {"own", "other", "other_child"}),
        ("$and", {"child"}),
    ],
)
def test_lookup_boolean_scope(
    ch_server: ClickHouseTraceServer,
    lookup_project: str,
    operator: str,
    expected_ids: set[str],
) -> None:
    span_eq = {"$eq": [{"$getField": "span_id"}, {"$literal": "child"}]}
    agent_eq = {"$eq": [{"$getField": "agent_name"}, {"$literal": "Planner"}]}
    if operator == "$or":
        expr = {
            "$or": [
                span_eq,
                agent_eq,
                {"$eq": [{"$getField": "agent_name"}, {"$literal": "Other"}]},
            ]
        }
    elif operator == "$not":
        expr = {"$and": [{"$not": [span_eq]}, {"$not": [agent_eq]}]}
    elif operator == "$and":
        expr = {
            "$and": [
                span_eq,
                agent_eq,
                {"$eq": [{"$getField": "stage"}, {"$literal": "answer"}]},
            ]
        }
    else:
        raise AssertionError(operator)

    response = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=lookup_project,
            query=Query.model_validate({"$expr": expr}),
        )
    )
    assert response.total_count == len(expected_ids)
    assert {span.span_id for span in response.spans} == expected_ids


def test_lookup_grouped_identity(
    ch_server: ClickHouseTraceServer, lookup_project: str
) -> None:
    query = Query.model_validate(
        {
            "$expr": {
                "$eq": [
                    {"$getField": "span_id"},
                    {"$literal": "child"},
                ]
            }
        }
    )
    req = AgentSpansQueryReq(
        project_id=lookup_project,
        query=query,
        group_by=[AgentGroupByRef(source="column", key="agent_name")],
    )
    actual = ch_server.agent_spans_query(req)
    reference_query = Query.model_validate(
        {
            "$expr": {
                "$or": [
                    query.expr_.model_dump(by_alias=True),
                    query.expr_.model_dump(by_alias=True),
                ]
            }
        }
    )
    reference = ch_server.agent_spans_query(
        req.model_copy(update={"query": reference_query})
    )
    assert actual == reference
    assert actual.total_count == 1
    assert len(actual.groups) == 1
