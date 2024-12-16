from datetime import datetime

import pytest

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture
def project_id():
    return "test-project-123"


@pytest.fixture
def setup_test_data(project_id, client: WeaveClient):
    # client.project = project_id

    print("Setting up test data", project_id)

    @weave.op()
    def create_test_data(pid: str):
        return "hello " + pid

    create_test_data(project_id)
    create_test_data(project_id)
    create_test_data(project_id)
    create_test_data(project_id)

    obj_dataset = weave.Dataset(
        name=f"{project_id}/test-obj", rows=[{"id": "test-obj"}]
    )
    weave.publish(obj_dataset)

    call1 = create_test_data.calls()[0]
    call1.feedback.add_reaction("👍")

    # Create test cost
    cost_req = tsi.CostCreateReq(
        project_id=project_id,
        wb_user_id="test-user",
        costs={
            "gpt-4": tsi.LLMCostSchema(
                prompt_token_cost=0.01,
                completion_token_cost=0.02,
                prompt_token_cost_unit="USD/1K tokens",
                completion_token_cost_unit="USD/1K tokens",
            )
        },
    )
    client.server.cost_create(cost_req)


def test_permanently_delete_project_deletes_all_data(
    project_id, setup_test_data, client: WeaveClient
):
    client.project = project_id
    calls = client.server.calls_query_stream(tsi.CallsQueryReq(project_id=project_id))

    print("calls", list(calls))

    # Verify data exists before deletion
    assert len(list(calls)) == 4

    obj_query = client.server.objs_query(tsi.ObjQueryReq(project_id=project_id))
    assert len(obj_query.objs) == 2

    table_query = client.server.table_query(
        tsi.TableQueryReq(project_id=project_id, digest="latest")
    )
    assert len(table_query.rows) == 1

    feedback_query = tsi.FeedbackQueryReq(
        project_id=project_id, fields=["id", "feedback_type"]
    )
    assert len(client.server.feedback_query(feedback_query).result) == 1

    cost_query = tsi.CostQueryReq(project_id=project_id, fields=["id", "llm_id"])
    assert len(client.server.cost_query(cost_query).results) == 1

    # Execute permanent deletion
    client.server.permanently_delete_project(
        tsi.PermanentlyDeleteProjectReq(project_id=project_id)
    )

    # Verify all data is deleted
    calls1 = client.server.calls_query_stream(tsi.CallsQueryReq(project_id=project_id))
    assert len(list(calls1)) == 0

    obj_query = client.server.objs_query(tsi.ObjQueryReq(project_id=project_id))
    assert len(obj_query.objs) == 0

    table_query = client.server.table_query(
        tsi.TableQueryReq(project_id=project_id, digest="latest")
    )
    assert len(table_query.rows) == 0

    feedback_query = tsi.FeedbackQueryReq(
        project_id=project_id, fields=["id", "feedback_type"]
    )
    assert len(client.server.feedback_query(feedback_query).result) == 0

    cost_query = tsi.CostQueryReq(project_id=project_id, fields=["id", "llm_id"])
    assert len(client.server.cost_query(cost_query).results) == 0


def test_permanently_delete_project_with_nonexistent_project(client: WeaveClient):
    client.project = "exists"
    # Should not raise an error when deleting non-existent project
    nonexistent_project_id = "nonexistent"
    client.server.permanently_delete_project(
        tsi.PermanentlyDeleteProjectReq(project_id=nonexistent_project_id)
    )


def test_permanently_delete_project_does_not_affect_other_projects(
    project_id, setup_test_data, client: WeaveClient
):
    client.project = "other-project"
    # Create another project with data
    other_project_id = "other-project"
    other_call_start = tsi.StartedCallSchemaForInsert(
        id="idddddddddddd",
        started_at=datetime.now(),
        project_id=other_project_id,
        op_name="test_op",
        inputs={},
        attributes={},
        wb_user_id="test-user",
        trace_id="test-trace-id",
    )
    client.server.call_start(tsi.CallStartReq(start=other_call_start))

    # Delete first project
    client.server.permanently_delete_project(
        tsi.PermanentlyDeleteProjectReq(project_id=project_id)
    )

    # Verify other project's data still exists
    other_project_calls = list(
        client.server.calls_query_stream(tsi.CallsQueryReq(project_id=other_project_id))
    )
    assert len(other_project_calls) > 0


def test_permanently_delete_project_idempotency(
    project_id, setup_test_data, client: WeaveClient
):
    client.project = project_id
    # Delete project twice
    client.server.permanently_delete_project(
        tsi.PermanentlyDeleteProjectReq(project_id=project_id)
    )
    client.server.permanently_delete_project(
        tsi.PermanentlyDeleteProjectReq(project_id=project_id)
    )

    # Verify data remains deleted
    assert (
        len(
            list(
                client.server.calls_query_stream(
                    tsi.CallsQueryReq(project_id=project_id)
                )
            )
        )
        == 0
    )
