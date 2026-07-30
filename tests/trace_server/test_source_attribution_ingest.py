"""Functional tests: source attribution end to end against real ClickHouse.

Proves migration 040 landed and the ingest paths populate it on all three
row-bearing tables — `spans`, `calls_merged` (via `call_parts`), and
`calls_complete` — and that the values are readable back through the public
query APIs, not just the raw columns.
"""

import datetime
import uuid

import pytest
from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource as PbResource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans,
    ScopeSpans,
    Span,
)

from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from tests.trace_server.conftest import TEST_ENTITY
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from tests.trace_server.helpers import force_optimize_calls_merged
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpansQueryReq,
    GenAIOTelExportReq,
)
from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import CallsStorageServerMode
from weave.trace_server.source_attribution import (
    INGEST_SOURCE_OTLP,
    INGEST_SOURCE_WEAVE,
)

pytestmark = pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND,
    reason="ClickHouse-only: asserts raw source_* columns and table residence",
)

SOURCE_COLUMNS = ("source_name", "source_version", "ingest_source")


@pytest.fixture
def clickhouse_trace_server(trace_server):
    """The internal ClickHouse server, with residence-based routing enabled."""
    internal_server = trace_server._internal_trace_server
    assert isinstance(internal_server, ClickHouseTraceServer)
    internal_server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return internal_server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source_rows(
    ch_client, table: str, project_id: str, key_column: str
) -> dict[str, tuple]:
    """Read the source_* columns for a project, keyed by `key_column`."""
    pb = ParamBuilder()
    project_slot = param_slot(pb.add_param(project_id), "String")
    columns = ", ".join(SOURCE_COLUMNS)
    result = ch_client.query(
        f"SELECT {key_column}, {columns} FROM {table} WHERE project_id = {project_slot}",
        parameters=pb.get_params(),
    )
    return {row[0]: tuple(row[1:]) for row in result.result_rows}


def _seed_calls_merged_residence(ch_client, project_id: str) -> None:
    """Pin a project to calls_merged so the v1 call API stays available."""
    pb = ParamBuilder()
    project_slot = param_slot(pb.add_param(project_id), "String")
    id_slot = param_slot(pb.add_param(str(uuid.uuid4())), "String")
    trace_slot = param_slot(pb.add_param(str(uuid.uuid4())), "String")
    ch_client.command(
        f"""
        INSERT INTO calls_merged (
            project_id, id, op_name, started_at, trace_id, parent_id,
            attributes_dump, inputs_dump, output_dump, summary_dump
        ) SELECT {project_slot}, {id_slot}, 'seed_op', now(), {trace_slot}, '',
            '{{}}', '{{}}', 'null', '{{}}'
        """,
        parameters=pb.get_params(),
    )


def _integration_attributes(name: str, version: str) -> dict:
    """The nested block `apply_integration_metadata` merges into call attributes."""
    return {
        "integration": {
            "name": name,
            "version": version,
            "meta": {"package_name": name, "package_version": "1.99.0"},
        }
    }


def _pb_span(name: str, attributes: dict[str, str]) -> Span:
    span = Span()
    span.name = name
    span.trace_id = uuid.uuid4().bytes
    span.span_id = uuid.uuid4().bytes[:8]
    now_ns = int(datetime.datetime.now().timestamp() * 1_000_000_000)
    span.start_time_unix_nano = now_ns
    span.end_time_unix_nano = now_ns + 1_000_000_000
    span.kind = 3
    for key, value in attributes.items():
        kv = KeyValue()
        kv.key = key
        kv.value.string_value = value
        span.attributes.append(kv)
    return span


def _processed_resource_spans(
    project: str,
    scope_groups: list[tuple[str, str, list[Span]]],
    resource_attributes: dict[str, str] | None = None,
) -> tsi.ProcessedResourceSpans:
    """Bundle spans into one payload, one ScopeSpans group per scope."""
    resource = PbResource()
    for key, value in (resource_attributes or {}).items():
        kv = KeyValue()
        kv.key = key
        kv.value.string_value = value
        resource.attributes.append(kv)

    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(resource)
    for scope_name, scope_version, spans in scope_groups:
        scope = InstrumentationScope()
        scope.name = scope_name
        scope.version = scope_version
        scope_spans = ScopeSpans()
        scope_spans.scope.CopyFrom(scope)
        for span in spans:
            scope_spans.spans.append(span)
        resource_spans.scope_spans.append(scope_spans)

    return tsi.ProcessedResourceSpans(
        entity=TEST_ENTITY,
        project=project,
        run_id=None,
        resource_spans=resource_spans,
    )


def _source_name_eq(value: str) -> Query:
    return Query(
        **{
            "$expr": {
                "$eq": [{"$getField": "source_name"}, {"$literal": value}],
            }
        }
    )


# ---------------------------------------------------------------------------
# spans
# ---------------------------------------------------------------------------


def test_spans_ingest_populates_and_queries_source_columns(
    trace_server, clickhouse_trace_server
):
    """One OTLP payload, three scopes: stamped, scope-only, and unattributable.

    The scope-only group is the point of the whole change — a raw-OTel sender
    that stamps nothing gets attributed with no client-side work.
    """
    project = "source_attr_spans"
    project_id = f"{TEST_ENTITY}/{project}"
    internal_project_id = b64(project_id)

    stamped = _pb_span(
        "chat gpt-5",
        {
            "gen_ai.operation.name": "chat",
            "integration.name": "openai",
            "integration.version": "0.53.1",
            "integration.meta.package_name": "openai",
        },
    )
    scope_only = _pb_span("chat claude", {"gen_ai.operation.name": "chat"})
    bare = _pb_span("chat mystery", {"gen_ai.operation.name": "chat"})

    processed = _processed_resource_spans(
        project,
        [
            # The stamped span's explicit attrs must beat this scope.
            ("opentelemetry.instrumentation.httpx", "0.1.0", [stamped]),
            ("opentelemetry.instrumentation.anthropic", "0.40.1", [scope_only]),
            ("", "", [bare]),
        ],
        # Resource service identity is intentionally not source attribution.
        resource_attributes={"service.name": "producer-app", "service.version": "9"},
    )

    res = trace_server.genai_otel_export(
        GenAIOTelExportReq(
            processed_spans=[processed],
            project_id=project_id,
            wb_user_id="test_user",
        )
    )
    assert (res.accepted_spans, res.rejected_spans) == (3, 0)

    by_span_name = _source_rows(
        clickhouse_trace_server.ch_client, "spans", internal_project_id, "span_name"
    )
    assert by_span_name == {
        "chat gpt-5": ("openai", "0.53.1", INGEST_SOURCE_OTLP),
        "chat claude": ("anthropic", "0.40.1", INGEST_SOURCE_OTLP),
        "chat mystery": ("", "", INGEST_SOURCE_OTLP),
    }

    # The promoted keys no longer leak into the custom-attr overflow map, but
    # integration.meta.* still does.
    pb = ParamBuilder()
    project_slot = param_slot(pb.add_param(internal_project_id), "String")
    custom_attrs = clickhouse_trace_server.ch_client.query(
        f"SELECT custom_attrs_string FROM spans "
        f"WHERE project_id = {project_slot} AND span_name = 'chat gpt-5'",
        parameters=pb.get_params(),
    ).result_rows[0][0]
    assert "integration.name" not in custom_attrs
    assert custom_attrs["integration.meta.package_name"] == "openai"

    # Filterable as a column, not a JSON scan.
    filtered = trace_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, query=_source_name_eq("anthropic"))
    )
    assert [s.span_name for s in filtered.spans] == ["chat claude"]
    assert filtered.spans[0].source_version == "0.40.1"
    assert filtered.spans[0].ingest_source == INGEST_SOURCE_OTLP

    # And groupable, which is the "who is sending us traffic" question.
    grouped = trace_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="field", key="source_name")],
        )
    )
    counts = {row.group_keys["source_name"]: row.span_count for row in grouped.groups}
    assert counts == {"openai": 1, "anthropic": 1, "": 1}


# ---------------------------------------------------------------------------
# calls_merged and calls_complete
# ---------------------------------------------------------------------------


def test_calls_merged_source_columns_from_call_parts(
    trace_server, clickhouse_trace_server
):
    """The v1 start/end split: only the start part carries attribution.

    The end part writes NULL and `anySimpleState` skips it, so the merged row
    must still show the start part's values.
    """
    project_id = f"{TEST_ENTITY}/source_attr_merged"
    internal_project_id = b64(project_id)
    ch_client = clickhouse_trace_server.ch_client
    _seed_calls_merged_residence(ch_client, internal_project_id)

    call_id = str(uuid.uuid4())
    started_at = datetime.datetime.now(datetime.timezone.utc)
    trace_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=str(uuid.uuid4()),
                op_name="attributed_op",
                started_at=started_at,
                attributes=_integration_attributes("langchain", "0.54.0"),
                inputs={"x": 1},
            )
        )
    )
    trace_server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                ended_at=started_at + datetime.timedelta(seconds=1),
                output={"y": 2},
                summary={},
            )
        )
    )

    # call_parts holds two rows: the start carries attribution, the end is NULL.
    pb = ParamBuilder()
    project_slot = param_slot(pb.add_param(internal_project_id), "String")
    id_slot = param_slot(pb.add_param(call_id), "String")
    columns = ", ".join(SOURCE_COLUMNS)
    parts = clickhouse_trace_server.ch_client.query(
        f"SELECT started_at IS NOT NULL, {columns} FROM call_parts "
        f"WHERE project_id = {project_slot} AND id = {id_slot}",
        parameters=pb.get_params(),
    ).result_rows
    assert sorted(parts) == [
        (False, None, None, None),
        (True, "langchain", "0.54.0", INGEST_SOURCE_WEAVE),
    ]

    force_optimize_calls_merged(ch_client)
    merged = _source_rows(ch_client, "calls_merged", internal_project_id, "id")
    assert merged[call_id] == ("langchain", "0.54.0", INGEST_SOURCE_WEAVE)

    calls = list(
        trace_server.calls_query_stream(tsi.CallsQueryReq(project_id=project_id))
    )
    attributed = [c for c in calls if c.id == call_id]
    assert len(attributed) == 1
    assert attributed[0].source_name == "langchain"
    assert attributed[0].source_version == "0.54.0"
    assert attributed[0].ingest_source == INGEST_SOURCE_WEAVE

    # The seeded row has no attribution: NULL reads back as None, not ''.
    seeded = [c for c in calls if c.op_name == "seed_op"]
    assert len(seeded) == 1
    assert (seeded[0].source_name, seeded[0].source_version) == (None, None)

    filtered = list(
        trace_server.calls_query_stream(
            tsi.CallsQueryReq(project_id=project_id, query=_source_name_eq("langchain"))
        )
    )
    assert [c.id for c in filtered] == [call_id]


def test_calls_complete_source_columns(trace_server, clickhouse_trace_server):
    """calls_complete stores the '' sentinel, and the read path maps it to None."""
    project_id = f"{TEST_ENTITY}/source_attr_complete"
    internal_project_id = b64(project_id)
    started_at = datetime.datetime.now(datetime.timezone.utc)

    attributed_id = str(uuid.uuid4())
    bare_id = str(uuid.uuid4())
    trace_server.calls_complete(
        tsi.CallsUpsertCompleteReq(
            batch=[
                tsi.CompletedCallSchemaForInsert(
                    project_id=project_id,
                    id=attributed_id,
                    trace_id=str(uuid.uuid4()),
                    op_name="attributed_op",
                    started_at=started_at,
                    ended_at=started_at + datetime.timedelta(seconds=1),
                    attributes=_integration_attributes("openai", "0.53.1"),
                    inputs={"x": 1},
                    output={"y": 2},
                    summary={},
                ),
                tsi.CompletedCallSchemaForInsert(
                    project_id=project_id,
                    id=bare_id,
                    trace_id=str(uuid.uuid4()),
                    op_name="bare_op",
                    started_at=started_at,
                    ended_at=started_at + datetime.timedelta(seconds=1),
                    attributes={"weave.ingest_source": "otlp"},
                    inputs={},
                    output=None,
                    summary={},
                    otel_dump={"name": "client-supplied"},
                ),
            ]
        )
    )

    rows = _source_rows(
        clickhouse_trace_server.ch_client,
        "calls_complete",
        internal_project_id,
        "id",
    )
    assert rows[attributed_id] == ("openai", "0.53.1", INGEST_SOURCE_WEAVE)
    # A plain @weave.op stamps nothing, so name/version are the '' sentinel --
    # but the surface is still recorded.
    assert rows[bare_id] == ("", "", INGEST_SOURCE_WEAVE)

    calls = {
        c.id: c
        for c in trace_server.calls_query_stream(
            tsi.CallsQueryReq(project_id=project_id)
        )
    }
    assert calls[attributed_id].source_name == "openai"
    assert calls[attributed_id].source_version == "0.53.1"
    assert calls[attributed_id].ingest_source == INGEST_SOURCE_WEAVE
    # '' round-trips to None so the calls read surface matches calls_merged.
    assert calls[bare_id].source_name is None
    assert calls[bare_id].source_version is None
    assert calls[bare_id].ingest_source == INGEST_SOURCE_WEAVE

    filtered = list(
        trace_server.calls_query_stream(
            tsi.CallsQueryReq(project_id=project_id, query=_source_name_eq("openai"))
        )
    )
    assert [c.id for c in filtered] == [attributed_id]


def test_otel_calls_export_attributes_from_otel_dump(
    trace_server, clickhouse_trace_server
):
    """OTel-ingested calls resolve explicit attributes before scope.

    Both survive only in otel_dump after Span.to_call normalizes call attributes.
    """
    project = "source_attr_otel_calls"
    project_id = f"{TEST_ENTITY}/{project}"
    internal_project_id = b64(project_id)

    processed = _processed_resource_spans(
        project,
        [
            (
                "openinference.instrumentation.bedrock",
                "0.3.1",
                [_pb_span("chat scope", {})],
            ),
            (
                "opentelemetry.instrumentation.httpx",
                "0.1.0",
                [
                    _pb_span(
                        "chat explicit",
                        {
                            "gen_ai.operation.name": "chat",
                            "integration.name": "openai",
                            "integration.version": "0.53.1",
                        },
                    )
                ],
            ),
            ("", "", [_pb_span("chat resource only", {})]),
        ],
        resource_attributes={"service.name": "lower-rung-loses"},
    )
    trace_server.otel_export(
        tsi.OTelExportReq(
            project_id=project_id,
            processed_spans=[processed],
            wb_user_id="test_user",
        )
    )

    # An empty project routes OTel writes to calls_complete.
    rows = _source_rows(
        clickhouse_trace_server.ch_client,
        "calls_complete",
        internal_project_id,
        "id",
    )
    assert sorted(rows.values()) == [
        ("", "", INGEST_SOURCE_OTLP),
        ("bedrock", "0.3.1", INGEST_SOURCE_OTLP),
        ("openai", "0.53.1", INGEST_SOURCE_OTLP),
    ]

    calls = {
        call.source_name: call
        for call in trace_server.calls_query_stream(
            tsi.CallsQueryReq(project_id=project_id)
        )
    }
    assert set(calls) == {None, "bedrock", "openai"}
    assert calls["bedrock"].source_version == "0.3.1"
    assert calls["openai"].source_version == "0.53.1"
    assert {call.ingest_source for call in calls.values()} == {INGEST_SOURCE_OTLP}


def test_otel_calls_export_to_calls_merged_project(
    trace_server, clickhouse_trace_server
):
    """The same OTel call, routed to calls_merged, lands the same attribution."""
    project = "source_attr_otel_merged"
    project_id = f"{TEST_ENTITY}/{project}"
    internal_project_id = b64(project_id)
    ch_client = clickhouse_trace_server.ch_client
    _seed_calls_merged_residence(ch_client, internal_project_id)

    processed = _processed_resource_spans(
        project,
        [("codex", "1.4.0", [_pb_span("chat", {})])],
    )
    trace_server.otel_export(
        tsi.OTelExportReq(
            project_id=project_id,
            processed_spans=[processed],
            wb_user_id="test_user",
        )
    )

    force_optimize_calls_merged(ch_client)
    rows = _source_rows(ch_client, "calls_merged", internal_project_id, "id")
    # The seeded residence row is unattributed; the OTel-ingested call is not.
    assert sorted(rows.values(), key=lambda v: v[0] or "") == [
        (None, None, None),
        ("codex", "1.4.0", INGEST_SOURCE_OTLP),
    ]
