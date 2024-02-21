import weave
from ..trace_server import trace_server_interface as tsi


def test_simple_op(trace_client):
    @weave.op()
    def my_op(a: int) -> int:
        return a + 1

    assert my_op(5) == 6

    op_ref = weave.obj_ref(my_op)
    assert trace_client.ref_is_own(op_ref)
    got_op = weave.storage.get(str(op_ref))

    runs = trace_client.runs()
    assert len(runs) == 1
    assert (
        runs[0].name
        == "wandb-trace://test_entity/test_project/op/op-my_op:d974fac56411d5e5b6cf75fad9a53811"
    )
    assert runs[0] == tsi.CallSchema(
        entity=trace_client.entity,
        project=trace_client.project,
        id=runs[0].id,
        name=runs[0].name,
        trace_id=runs[0].trace_id,
        parent_id=None,
        status_code=tsi.StatusCodeEnum.OK,
        start_time_s=float(runs[0].start_time_s),
        end_time_s=float(runs[0].end_time_s),
        exception=None,
        attributes=None,
        inputs=None,
        outputs={"_result": 6},
        summary=None,
    )


def test_dataset(trace_client):
    from weave.weaveflow import Dataset

    d = Dataset([{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    ref = weave.publish(d)
    d2 = weave.storage.get(str(ref))
    assert d2.rows == d2.rows


def test_trace_server_call_create(clickhouse_trace_server):
    req_call = tsi.PartialCallForCreationSchema(
                entity="test_entity",
                project="test_project",
                id="test_id",

                name="test_name",

                trace_id="test_trace_id",
                parent_id="test_parent_id",

                status_code=tsi.StatusCodeEnum.OK,
                start_time_s=0.0,
                end_time_s=1.0,
                exception=None,

                attributes={"a": 5},
                inputs={"b": 5},
                outputs={"c": 5},
                summary={"d": 5},
            )
    clickhouse_trace_server.call_create(
        tsi.CallCreateReq(
            call=req_call
        )
    )

    res = clickhouse_trace_server.call_read(
        tsi.CallReadReq(
            entity="test_entity",
            project="test_project",
            id="test_id",
        )
    )

    assert res.call.model_dump() == req_call.model_dump()


