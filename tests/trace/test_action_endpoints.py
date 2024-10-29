from typing import Optional

from redis import Redis

import weave
from weave.actions_worker.celery_app import app as celery_app
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import (
    ActionsAckBatchReq,
    ClickHouseTraceServer,
)
from weave.trace_server.interface.base_models.action_base_models import (
    ConfiguredAction,
    ConfiguredContainsWordsAction,
)
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def assert_num_actions_in_queue(num_actions: int):
    redis = Redis.from_url(celery_app.conf.result_backend)
    # all_task_ids = redis.keys("celery-task-meta-*")
    queue_name = "celery"
    tasks = redis.lrange(queue_name, 0, -1)  # Get all tasks in the queue

    assert len(tasks) == num_actions


def test_actions_execute_batch(client: WeaveClient):
    # TODO: This is neither unit test nor integration test. It's a bit of both.
    is_sqlite = isinstance(client.server._internal_trace_server, SqliteTraceServer)  # type: ignore
    if is_sqlite:
        # dont run this test for sqlite
        return

    # Step 1: Create a configured action.
    digest = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": "test_object",
                    "base_object_class": "ConfiguredAction",
                    "val": ConfiguredAction(
                        name="test_action",
                        config=ConfiguredContainsWordsAction(
                            target_words=["mindful", "demure"]
                        ),
                    ).model_dump(),
                }
            }
        )
    ).digest
    action_ref_uri = ObjectRef(
        entity=client.entity,
        project=client.project,
        name="test_object",
        _digest=digest,
    ).uri()

    # Step 2: Create an op.
    @weave.op
    def example_op(input: str) -> str:
        return input + "; on second thought, maybe not"

    _, call1 = example_op.call("i would like a bagel")
    _, call2 = example_op.call("i would like a coffee")

    # Step 3: Execute the action.
    server = client.server
    res = server.actions_execute_batch(
        tsi.ActionsExecuteBatchReq(
            project_id=client._project_id(),
            call_ids=[call1.id, call2.id],
            id="1",
            configured_action_ref=action_ref_uri,
        )
    )
    assert res.id == "1"

    # Warning: Test hacks below. This endpoint doesn't have an equivalent read endpoint, so we're going to verify correct behavior by inspecting the CH table directly.
    ch_client = ClickHouseTraceServer.from_env().ch_client
    query_res = ch_client.query("""
    SELECT project_id,
           call_id,
           id,
           any(configured_action),  # Updated column name
           max(created_at),
           max(finished_at),
           max(failed_at)
    FROM actions_merged
    GROUP BY project_id, call_id, id
    ORDER BY call_id ASC
    """)
    rows = list(query_res.named_results())
    # TODO(Tim): This is ugly and bad..we need a better pattern.
    db_project_id = client.server.server._idc.ext_to_int_project_id(
        client._project_id()
    )  # type: ignore
    assert len(rows) == 2
    assert {
        "project_id": rows[0]["project_id"],
        "call_id": rows[0]["call_id"],
        "id": rows[0]["id"],
    } == {"project_id": db_project_id, "call_id": call1.id, "id": "1"}
    assert {
        "project_id": rows[1]["project_id"],
        "call_id": rows[1]["call_id"],
        "id": rows[1]["id"],
    } == {"project_id": db_project_id, "call_id": call2.id, "id": "1"}

    # Ok, if we got to here, we've successfully added two actions to the table.
    # Now let's check to see everything made it into the queue.
    assert_num_actions_in_queue(2)


def test_actions_ack_batch(client: WeaveClient):
    # Build on previous test by adding an action and then acking it.
    server = client.server
    exec_res = server.actions_execute_batch(
        tsi.ActionsExecuteBatchReq(
            project_id=client._project_id(),
            call_ids=["3", "4"],
            id="1",
            configured_action_ref="weave://shawn/test-project/test_object",
        )
    )
    assert exec_res.id == "1"

    # Another unfortunate hack...actions_ack_batch is private and not part of the public server interface.
    ch_server: Optional[ClickHouseTraceServer] = None
    if isinstance(server._internal_trace_server, ClickHouseTraceServer):  # type: ignore
        ch_server = server._internal_trace_server  # type: ignore
    else:
        raise ValueError("Test only works with ClickHouseTraceServer")

    db_project_id = client.server.server._idc.ext_to_int_project_id(  # type: ignore
        client._project_id()
    )

    # Ack call_id 3.
    ack_res = ch_server.actions_ack_batch(
        ActionsAckBatchReq(
            project_id=db_project_id, call_ids=["3"], id="1", succeeded=True
        )
    )
    assert ack_res.id == "1"
    ch_client = ClickHouseTraceServer.from_env().ch_client

    query_res = ch_client.query(f"""
    SELECT project_id,
           call_id,
           id,
           any(configured_action) as configured_action,
           max(created_at) as created_at,
           max(finished_at) as finished_at,
           max(failed_at) as failed_at
    FROM actions_merged
    WHERE project_id = '{db_project_id}' AND id = '1'
    GROUP BY project_id, call_id, id
    ORDER BY call_id ASC
    """)
    rows = list(query_res.named_results())
    assert len(rows) == 2
    assert rows[0]["finished_at"] is not None
    assert rows[1]["finished_at"] is None
    # call_id 1 should now be finished, but call_id 2 should not.

    # Now let's ack call_id 4.
    ack_res = ch_server.actions_ack_batch(
        ActionsAckBatchReq(
            project_id=db_project_id, call_ids=["4"], id="1", succeeded=False
        )
    )
    assert ack_res.id == "1"
    query_res = ch_client.query(f"""
    SELECT project_id,
           call_id,
           id,
           any(configured_action) as configured_action,
           max(created_at) as created_at,
           max(finished_at) as finished_at,
           max(failed_at) as failed_at
    FROM actions_merged
    WHERE project_id = '{db_project_id}' AND id = '1'
    GROUP BY project_id, call_id, id
    ORDER BY call_id ASC
    """)
    rows = list(query_res.named_results())
    assert len(rows) == 2
    assert rows[1]["finished_at"] is None
    assert rows[1]["failed_at"] is not None
