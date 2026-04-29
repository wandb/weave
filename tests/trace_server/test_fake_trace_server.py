from __future__ import annotations

import datetime

from tests.trace_server.conftest_lib.fake_trace_server import FakeTraceServer
from weave.shared import compute_file_digest, refs_internal
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy


def _dt(seconds: int = 0) -> datetime.datetime:
    return datetime.datetime(2026, 1, 1, 0, 0, seconds, tzinfo=datetime.timezone.utc)


def test_fake_trace_server_calls_lifecycle_query_and_delete() -> None:
    server = FakeTraceServer()
    project_id = "project"

    start_res = server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id="call-1",
                op_name="predict",
                started_at=_dt(),
                attributes={"env": "test"},
                inputs={"x": 1},
            )
        )
    )
    assert start_res.id == "call-1"

    server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id="call-1",
                ended_at=_dt(1),
                output={"y": 2},
                summary={},
            )
        )
    )

    query = tsi.Query(
        **{
            "$expr": {
                "$eq": [
                    {"$getField": "op_name"},
                    {"$literal": "predict"},
                ]
            }
        }
    )
    calls = server.calls_query(
        tsi.CallsQueryReq(project_id=project_id, query=query)
    ).calls
    assert [call.id for call in calls] == ["call-1"]
    assert server.call_read(tsi.CallReadReq(project_id=project_id, id="call-1")).call

    server.call_update(
        tsi.CallUpdateReq(project_id=project_id, call_id="call-1", display_name="P")
    )
    assert (
        server.call_read(tsi.CallReadReq(project_id=project_id, id="call-1"))
        .call.display_name
        == "P"
    )

    deleted = server.calls_delete(
        tsi.CallsDeleteReq(project_id=project_id, call_ids=["call-1"])
    )
    assert deleted.num_deleted == 1
    assert server.calls_query(tsi.CallsQueryReq(project_id=project_id)).calls == []


def test_fake_trace_server_objects_tables_files_refs_and_stats() -> None:
    server = FakeTraceServer()
    project_id = "project"

    table_res = server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=project_id,
                rows=[{"id": 2}, {"id": 1}],
            )
        )
    )
    sorted_rows = server.table_query(
        tsi.TableQueryReq(
            project_id=project_id,
            digest=table_res.digest,
            sort_by=[SortBy(field="id", direction="asc")],
        )
    ).rows
    assert [row.val["id"] for row in sorted_rows] == [1, 2]

    obj_res = server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj",
                val={
                    "nested": {"x": 1},
                    "rows": refs_internal.InternalTableRef(
                        project_id=project_id, digest=table_res.digest
                    ).uri,
                },
            )
        )
    )
    obj = server.obj_read(
        tsi.ObjReadReq(project_id=project_id, object_id="obj", digest="latest")
    ).obj
    assert obj.digest == obj_res.digest

    refs = server.refs_read_batch(
        tsi.RefsReadBatchReq(
            refs=[
                refs_internal.InternalObjectRef(
                    project_id=project_id,
                    name="obj",
                    version=obj_res.digest,
                    extra=["key", "nested", "key", "x"],
                ).uri,
                refs_internal.InternalTableRef(
                    project_id=project_id, digest=table_res.digest
                ).uri,
            ]
        )
    ).vals
    assert refs == [1, [{"id": 2}, {"id": 1}]]

    content = b"hello"
    file_res = server.file_create(
        tsi.FileCreateReq(project_id=project_id, name="hello.txt", content=content)
    )
    assert file_res.digest == compute_file_digest(content)
    assert (
        server.file_content_read(
            tsi.FileContentReadReq(project_id=project_id, digest=file_res.digest)
        ).content
        == content
    )

    stats = server.project_stats(
        tsi.ProjectStatsReq(
            project_id=project_id,
            include_object_storage_size=True,
            include_table_storage_size=True,
            include_file_storage_size=True,
        )
    )
    assert stats.objects_storage_size_bytes > 0
    assert stats.tables_storage_size_bytes > 0
    assert stats.files_storage_size_bytes == len(content)


def test_fake_trace_server_feedback_and_costs() -> None:
    server = FakeTraceServer()
    project_id = "project"

    feedback = server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref="weave-trace-internal:///project/call/call-1",
            feedback_type="note",
            payload={"score": 1},
        )
    )
    assert feedback.payload == {"score": 1}
    assert (
        server.feedback_query(
            tsi.FeedbackQueryReq(project_id=project_id, fields=["count(*)"])
        ).result[0]["count(*)"]
        == 1
    )

    server.cost_create(
        tsi.CostCreateReq(
            project_id=project_id,
            costs={
                "gpt-test": tsi.CostCreateInput(
                    prompt_token_cost=1.0,
                    completion_token_cost=2.0,
                    prompt_token_cost_unit="USD",
                    completion_token_cost_unit="USD",
                    effective_date=_dt(),
                    provider_id="test",
                )
            },
        )
    )
    costs = server.cost_query(tsi.CostQueryReq(project_id=project_id)).results
    assert len(costs) == 1
    assert costs[0].llm_id == "gpt-test"
