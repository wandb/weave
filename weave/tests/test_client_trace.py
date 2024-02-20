import typing
import pytest
from clickhouse_connect import get_client

import weave
from weave.weave_init import InitializedClient
from ..trace_server import (
    graph_client_trace,
    clickhouse_trace_server_batched,
    trace_server_interface,
)


@pytest.fixture()
def trace_client():
    clickhouse_trace_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
        "localhost", 8123, False
    )
    graph_client = graph_client_trace.GraphClientTrace(clickhouse_trace_server)
    inited_client = InitializedClient(graph_client)

    try:
        yield graph_client
    finally:
        inited_client.reset()


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
    assert runs[0] == trace_server_interface.CallSchema(
        entity="test_entity",
        project="test_project",
        id=runs[0].id,
        name=runs[0].name,
        trace_id=runs[0].trace_id,
        parent_id=None,
        status_code=trace_server_interface.StatusCodeEnum.OK,
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


def test_dumb_test():
    import weave

    weave.init("test-project-weave")

    @weave.op()
    def do_it(a):
        return a + 1

    do_it(1)
