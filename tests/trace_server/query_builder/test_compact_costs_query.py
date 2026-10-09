import datetime
import json
import uuid
from pathlib import Path

import pytest

from tests.trace_server.query_builder.utils import assert_raw_sql
from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import CallsQuery
from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable

PROJECT = "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc="
START = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
FIELDS = [
    "id",
    "project_id",
    "trace_id",
    "parent_id",
    "op_name",
    "started_at",
    "ended_at",
    "exception",
    "display_name",
    "inputs_dump",
    "output_dump",
    "attributes_dump",
    "summary_dump",
]


def make_query(read_table, compact, sort, narrow=False, limit=None, offset=None):
    query = CallsQuery(
        project_id=PROJECT,
        read_table=read_table,
        include_costs=True,
        costs_have_unique_call_keys=compact,
    )
    for field in ["id", "started_at", "summary_dump"] if narrow else FIELDS:
        query.add_field(field)
    if sort:
        query.add_order(sort, "desc")
        query.add_order("id", "asc")
    if limit is not None:
        query.set_limit(limit)
    if offset is not None:
        query.set_offset(offset)
    return query


@pytest.fixture
def seeded_calls(ch_server, request, monkeypatch):
    monkeypatch.setenv("WF_CLICKHOUSE_COMPACT_COST_QUERIES", "true")
    read_table = request.param
    price_ids = []
    for year, rate in [(2023, 0.001), (2024, 0.002), (2026, 0.009)]:
        created = ch_server.cost_create(
            tsi.CostCreateReq(
                project_id=PROJECT,
                costs={
                    model: {
                        "prompt_token_cost": rate,
                        "completion_token_cost": rate * 2,
                        "cache_read_input_token_cost": rate / 2,
                        "cache_creation_input_token_cost": rate * 3,
                        "effective_date": START.replace(year=year),
                    }
                    for model in ["compact-model-a", "compact-model-b"]
                },
                wb_user_id="user",
            )
        )
        price_ids.extend(price_id for price_id, _ in created.ids)
    ch_server.cost_create(
        tsi.CostCreateReq(
            project_id="foreign-project",
            costs={
                "compact-model-a": {
                    "prompt_token_cost": 99,
                    "completion_token_cost": 99,
                }
            },
            wb_user_id="user",
        )
    )
    usage = {
        model: {
            "requests": 1,
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "cache_read_input_tokens": 20,
            "cache_creation_input_tokens": 10,
        }
        for model in ["compact-model-a", "compact-model-b"]
    }
    for i, summary in enumerate(
        [
            {"usage": usage, "score": 4},
            {"usage": usage, "score": 1},
            {"score": 2},
            {"usage": {"missing-model": {"input_tokens": 10}}, "score": 3},
        ]
    ):
        summary["large"] = "summary" * 20000
        start = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=PROJECT,
                id=str(uuid.UUID(int=i + 1)),
                trace_id=str(uuid.UUID(int=i + 101)),
                op_name="test-op",
                started_at=START,
                attributes={"sort": i},
                inputs={"large": "input" * 20000, "i": i},
            )
        )
        end = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=PROJECT,
                id=str(uuid.UUID(int=i + 1)),
                started_at=START,
                ended_at=START + datetime.timedelta(seconds=i + 1),
                output={"large": "output" * 20000, "i": i},
                summary=summary,
            )
        )
        if read_table == ReadTable.CALLS_MERGED:
            ch_server.call_start(start)
            ch_server.call_end(end)
        else:
            ch_server.call_start_v2(start)
            ch_server.call_end_v2(end)
    yield ch_server, read_table
    ch_server.cost_purge(
        tsi.CostPurgeReq(
            project_id=PROJECT,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$in": [
                            {"$getField": "id"},
                            [{"$literal": price_id} for price_id in price_ids],
                        ]
                    }
                }
            ),
        )
    )


def execute(server, query, read_table):
    pb = ParamBuilder("pb")
    settings = (
        {**ch_settings.CLICKHOUSE_CALLS_COMPLETE_READ_SETTINGS, "final": 1}
        if read_table == ReadTable.CALLS_COMPLETE
        else {}
    )
    result = server.ch_client.query(
        query.as_sql(pb), parameters=pb.get_params(), settings=settings
    )
    return [
        {
            column: json.loads(value) if column == "summary_dump" else value
            for column, value in zip(result.column_names, row, strict=True)
        }
        for row in result.result_rows
    ]


@pytest.mark.parametrize("seeded_calls", list(ReadTable), indirect=True)
@pytest.mark.parametrize(
    ("sort", "narrow", "limit", "offset"),
    [
        ("started_at", False, None, None),
        ("summary.weave.status", False, 2, 1),
        ("attributes.sort", False, 3, None),
        ("summary.score", True, None, None),
        (None, False, None, None),
    ],
)
def test_compact_costs_preserve_results(seeded_calls, sort, narrow, limit, offset):
    server, read_table = seeded_calls
    baseline = execute(
        server, make_query(read_table, False, sort, narrow, limit, offset), read_table
    )
    compact = execute(
        server, make_query(read_table, True, sort, narrow, limit, offset), read_table
    )
    if not sort:
        baseline.sort(key=lambda row: row["id"])
        compact.sort(key=lambda row: row["id"])
    assert compact == baseline
    assert len(compact) == (limit or 4)
    if limit is None:
        priced = next(row for row in compact if row["id"] == str(uuid.UUID(int=1)))
        assert priced["summary_dump"]["usage"] == baseline[0]["summary_dump"]["usage"]
        for model in ["compact-model-a", "compact-model-b"]:
            cost = priced["summary_dump"]["weave"]["costs"][model]
            assert cost["prompt_token_cost"] == 0.002
            assert cost["prompt_tokens_total_cost"] == pytest.approx(0.14)
            assert cost["cache_read_input_tokens_total_cost"] == pytest.approx(0.02)
            assert cost["cache_creation_input_tokens_total_cost"] == pytest.approx(0.06)


def test_compact_costs_sql():
    query = make_query(ReadTable.CALLS_MERGED, True, "started_at", limit=2, offset=1)
    pb = ParamBuilder("pb")
    sql = query.as_sql(pb)
    expected = Path(__file__).with_name("compact_costs.sql").read_text()
    params = json.loads(
        Path(__file__).with_name("compact_costs.params.json").read_text()
    )
    assert_raw_sql(sql, expected, pb.get_params(), params)


def test_feedback_order_keeps_existing_cost_path():
    queries = []
    for compact in [False, True]:
        query = make_query(
            ReadTable.CALLS_MERGED, compact, "feedback.[wandb.runnable.x].payload"
        )
        pb = ParamBuilder("pb")
        queries.append((query.as_sql(pb), pb.get_params()))
    assert queries[0] == queries[1]


@pytest.mark.parametrize("read_table", list(ReadTable))
def test_unordered_page_keeps_existing_cost_path(read_table):
    queries = []
    for compact in [False, True]:
        query = make_query(read_table, compact, None, limit=3)
        pb = ParamBuilder("pb")
        queries.append((query.as_sql(pb), pb.get_params()))
    assert queries[0] == queries[1]


@pytest.mark.parametrize("seeded_calls", [ReadTable.CALLS_COMPLETE], indirect=True)
def test_final_preserves_same_id_with_different_started_at(seeded_calls):
    server, read_table = seeded_calls
    call_id = str(uuid.UUID(int=1))
    summary = json.dumps(
        {"usage": {"compact-model-b": {"input_tokens": 7, "output_tokens": 3}}}
    )
    server.ch_client.command(
        "INSERT INTO calls_complete "
        "SELECT * REPLACE ("
        "toDateTime64('2027-01-01 00:00:00', 3) AS started_at, "
        "{summary:String} AS summary_dump) "
        "FROM calls_complete FINAL WHERE project_id = {project:String} AND id = {id:String}",
        parameters={"project": PROJECT, "id": call_id, "summary": summary},
    )
    baseline = execute(server, make_query(read_table, False, "started_at"), read_table)
    compact = execute(server, make_query(read_table, True, "started_at"), read_table)
    assert compact == baseline
    versions = [row for row in compact if row["id"] == call_id]
    assert len(versions) == 2
    assert [row["started_at"].year for row in versions] == [2027, 2025]
    assert [set(row["summary_dump"]["weave"]["costs"]) for row in versions] == [
        {"compact-model-b"},
        {"compact-model-a"},
    ]


@pytest.mark.parametrize("seeded_calls", list(ReadTable), indirect=True)
def test_compact_costs_preserve_storage_fields(seeded_calls):
    server, read_table = seeded_calls
    rows = []
    for compact in [False, True]:
        query = make_query(read_table, compact, "started_at", limit=3)
        query.add_field("storage_size_bytes")
        query.add_field("total_storage_size_bytes")
        rows.append(execute(server, query, read_table))
    assert rows[0] == rows[1]


@pytest.mark.parametrize("seeded_calls", list(ReadTable), indirect=True)
def test_compact_costs_stream_full_payload(seeded_calls):
    server, read_table = seeded_calls
    calls = list(
        server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=PROJECT,
                include_costs=True,
                latest_only=read_table == ReadTable.CALLS_COMPLETE,
                limit=2,
            )
        )
    )
    assert [call.id for call in calls] == [str(uuid.UUID(int=i)) for i in [1, 2]]
    for i, call in enumerate(calls):
        assert call.inputs == {"large": "input" * 20000, "i": i}
        assert call.output == {"large": "output" * 20000, "i": i}
        assert call.attributes == {"sort": i}
        assert (
            call.summary["weave"]["costs"]["compact-model-a"]["prompt_token_cost"]
            == 0.002
        )


@pytest.mark.parametrize("seeded_calls", list(ReadTable), indirect=True)
def test_cost_query_flag_preserves_api_response(seeded_calls, monkeypatch):
    server, read_table = seeded_calls
    responses = []
    for enabled in ["false", "true"]:
        monkeypatch.setenv("WF_CLICKHOUSE_COMPACT_COST_QUERIES", enabled)
        calls = list(
            server.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=PROJECT,
                    columns=["id"],
                    include_costs=True,
                    latest_only=read_table == ReadTable.CALLS_COMPLETE,
                    limit=2,
                )
            )
        )
        responses.append([call.model_dump() for call in calls])
    assert responses[0] == responses[1]
    assert len(responses[0]) == 2


@pytest.mark.parametrize("sort", [None, "attributes.sort"])
def test_complete_page_without_full_call_key_order_keeps_existing_path(sort):
    queries = []
    for compact in [False, True]:
        query = make_query(ReadTable.CALLS_COMPLETE, compact, sort, limit=3)
        pb = ParamBuilder("pb")
        queries.append((query.as_sql(pb), pb.get_params()))
    assert queries[0] == queries[1]


@pytest.mark.parametrize("seeded_calls", list(ReadTable), indirect=True)
def test_compact_costs_read_call_relation_once(seeded_calls):
    server, read_table = seeded_calls
    query = make_query(read_table, True, "started_at", limit=3)
    pb = ParamBuilder("pb")
    rows = server.ch_client.query(
        "EXPLAIN indexes=1 " + query.as_sql(pb),
        parameters=pb.get_params(),
    ).result_rows
    plan = "\n".join(row[0] for row in rows)
    assert (
        sum(
            "ReadFromMergeTree" in line and read_table.value in line
            for line in plan.splitlines()
        )
        == 1
    ), plan


@pytest.mark.parametrize("seeded_calls", list(ReadTable), indirect=True)
def test_price_history_preserves_time_and_scope_precedence(seeded_calls):
    server, read_table = seeded_calls
    prefix = str(uuid.uuid4())
    prices = [
        (f"{prefix}-past-default", "project", PROJECT, 2026, 9.0),
        (f"{prefix}-past-default", "default", "default", 2024, 1.0),
        (f"{prefix}-past-project", "project", PROJECT, 2023, 2.0),
        (f"{prefix}-past-project", "default", "default", 2024, 1.0),
        (f"{prefix}-all-future", "project", PROJECT, 2026, 9.0),
        (f"{prefix}-all-future", "project", PROJECT, 2028, 3.0),
        (f"{prefix}-all-future", "default", "default", 2029, 1.0),
    ]
    for model, level, level_id, year, rate in prices:
        server.ch_client.command(
            "INSERT INTO llm_token_prices "
            "(id, llm_id, pricing_level, pricing_level_id, effective_date, "
            "prompt_token_cost, completion_token_cost) VALUES "
            "({id:String}, {model:String}, {level:String}, {level_id:String}, "
            "{effective:DateTime64(3)}, {rate:Float64}, {rate:Float64})",
            parameters={
                "id": str(uuid.uuid4()),
                "model": model,
                "level": level,
                "level_id": level_id,
                "effective": START.replace(year=year),
                "rate": rate,
            },
        )
    call_id = str(uuid.uuid4())
    start = tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id=PROJECT,
            id=call_id,
            trace_id=str(uuid.uuid4()),
            op_name="pricing-precedence",
            started_at=START,
            attributes={},
            inputs={},
        )
    )
    end = tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id=PROJECT,
            id=call_id,
            started_at=START,
            ended_at=START + datetime.timedelta(seconds=1),
            output={},
            summary={
                "usage": {
                    model: {"input_tokens": 10}
                    for model in [
                        f"{prefix}-past-default",
                        f"{prefix}-past-project",
                        f"{prefix}-all-future",
                    ]
                }
            },
        )
    )
    if read_table == ReadTable.CALLS_MERGED:
        server.call_start(start)
        server.call_end(end)
    else:
        server.call_start_v2(start)
        server.call_end_v2(end)
    baseline = execute(server, make_query(read_table, False, "started_at"), read_table)
    candidate = execute(server, make_query(read_table, True, "started_at"), read_table)
    assert candidate == baseline
    costs = next(row for row in candidate if row["id"] == call_id)["summary_dump"][
        "weave"
    ]["costs"]
    assert {model: cost["prompt_token_cost"] for model, cost in costs.items()} == {
        f"{prefix}-past-default": 1.0,
        f"{prefix}-past-project": 2.0,
        f"{prefix}-all-future": 3.0,
    }
