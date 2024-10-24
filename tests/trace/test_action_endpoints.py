import json

from redis import Redis

from weave.actions_worker.celery_app import app as celery_app
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer


def assert_num_actions_in_queue(num_actions: int):
    redis = Redis.from_url(celery_app.conf.result_backend)
    # all_task_ids = redis.keys("celery-task-meta-*")
    queue_name = "celery"
    tasks = redis.lrange(queue_name, 0, -1)  # Get all tasks in the queue

    assert len(tasks) == num_actions


def test_actions_execute_batch(client: WeaveClient):
    # TODO: This is neither unit test nor integration test. It's a bit of both.
    server = client.server
    res = server.actions_execute_batch(
        tsi.ActionsExecuteBatchReq(
            project_id=client.project,
            call_ids=["1", "2"],
            id="1",
            effect=json.dumps(
                {
                    "task": "wordcount",
                    "kwargs": {
                        "payload": "hello world, i am so happy to be rushing this feature for friday"
                    },
                }
            ),
        )
    )
    assert res.id == "1"

    # Warning: Test hacks below. This endpoint doesn't have an equivalent read endpoint, so we're going to verify correct behavior by inspecting the CH table directly.
    ch_client = ClickHouseTraceServer.from_env().ch_client
    query_res = ch_client.query("""
    SELECT project_id,
           call_id,
           id,
           any(rule_matched),
           any(effect),
           max(created_at),
           max(finished_at),
           max(failed_at)
    FROM actions_merged
    GROUP BY project_id, call_id, id
    ORDER BY call_id ASC
    """)
    rows = list(query_res.named_results())
    # TODO(Tim): This is ugly and bad..we need a better pattern.
    db_project_id = client.server.server._idc.ext_to_int_project_id(client.project)  # type: ignore
    assert len(rows) == 2
    assert {
        "project_id": rows[0]["project_id"],
        "call_id": rows[0]["call_id"],
        "id": rows[0]["id"],
    } == {"project_id": db_project_id, "call_id": "1", "id": "1"}
    assert {
        "project_id": rows[1]["project_id"],
        "call_id": rows[1]["call_id"],
        "id": rows[1]["id"],
    } == {"project_id": db_project_id, "call_id": "2", "id": "1"}

    # Ok, if we got to here, we've successfully added two actions to the table.
    # Now let's check to see everything made it into the queue.
    assert_num_actions_in_queue(2)


def test_actions_ack_batch(client: WeaveClient):
    # Build on previous test by adding an action and then acking it.
    server = client.server
    exec_res = server.actions_execute_batch(
        tsi.ActionsExecuteBatchReq(
            project_id=client.project,
            call_ids=["3", "4"],
            id="1",
            effect=json.dumps({"task": "noop", "kwargs": {}}),
        )
    )
    assert exec_res.id == "1"

    # Ack call_id 3.
    ack_res = server.actions_ack_batch(
        tsi.ActionsAckBatchReq(
            project_id=client.project, call_ids=["3"], id="1", succeeded=True
        )
    )
    assert ack_res.id == "1"
    ch_client = ClickHouseTraceServer.from_env().ch_client
    db_project_id = client.server.server._idc.ext_to_int_project_id(client.project)  # type: ignore
    query_res = ch_client.query(f"""
    SELECT project_id,
           call_id,
           id,
           any(rule_matched) as rule_matched,
           any(effect) as effect,
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
    ack_res = server.actions_ack_batch(
        tsi.ActionsAckBatchReq(
            project_id=client.project, call_ids=["4"], id="1", succeeded=False
        )
    )
    assert ack_res.id == "1"
    query_res = ch_client.query(f"""
    SELECT project_id,
           call_id,
           id,
           any(rule_matched) as rule_matched,
           any(effect) as effect,
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
