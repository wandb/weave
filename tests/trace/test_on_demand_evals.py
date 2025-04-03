"""
This test suite is inteded to test the end to end lifecycle of on demand evaluations.
The end goal is to enable the user to configure, run, and analyze evaluations purely through the API.
"""

import weave
from weave import ObjectRef
from weave.trace.refs import TableRef
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import ObjCreateReq, TableCreateReq


def do_test_dataset_create(client: WeaveClient):
    TABLE_NAME = "test_dataset"
    ROWS = [
        {"input": "United States", "output": "USA"},
        {"input": "Canada", "output": "CAN"},
        {"input": "Mexico", "output": "MEX"},
    ]

    table_create_res = client.server.table_create(
        TableCreateReq.model_validate(
            {
                "table": {
                    "project_id": client._project_id(),
                    "rows": ROWS,
                }
            }
        )
    )
    table_digest = table_create_res.digest
    table_ref = TableRef(
        entity=client.entity,
        project=client.project,
        _digest=table_digest,
    )
    obj_create_res = client.server.obj_create(
        ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": TABLE_NAME,
                    "val": {
                        "_type": "Dataset",
                        "rows": table_ref.uri(),
                        "_class_name": "Dataset",
                        "_bases": ["Object", "BaseModel"],
                    },
                    # "builtin_object_class": "Dataset",
                }
            }
        )
    )
    obj_digest = obj_create_res.digest
    obj_ref = ObjectRef(
        entity=client.entity,
        project=client.project,
        name=TABLE_NAME,
        _digest=obj_digest,
    )
    gotten_dataset = obj_ref.get()
    assert isinstance(gotten_dataset, weave.Dataset)
    assert gotten_dataset.rows == ROWS

    return obj_ref


def test_llm_judge_scorer_create(client: WeaveClient):
    pass


def test_evaluation_create(client: WeaveClient):
    dataset_ref = do_test_dataset_create(client)
    pass


def test_model_create(client: WeaveClient):
    pass


def test_evaluation_run_remotely(client: WeaveClient):
    pass


def test_evaluation_run_locally(client: WeaveClient):
    pass


def test_list_evaluations(client: WeaveClient):
    pass


def test_list_evaluation_runs(client: WeaveClient):
    pass
