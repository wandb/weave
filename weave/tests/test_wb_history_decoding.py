import datetime
import time
import datetime

import pytest
import weave
from .. import context_state as _context
from PIL import Image
import numpy as np


from weave.wandb_client_api import wandb_gql_query, wandb_public_api
from weave.wandb_interface import wandb_stream_table


def image():
    imarray = np.random.rand(100, 100, 3) * 255
    return Image.fromarray(imarray.astype("uint8")).convert("RGBA")


_loading_builtins_token = _context.set_loading_built_ins()


@weave.type()
class TestType:
    a: int
    b: str


_context.clear_loading_built_ins(_loading_builtins_token)

base_types = {
    "number": 42,
    "string": "hello world",
    "boolean": True,
    "object": TestType(1, "hi"),
    "custom": image(),
}
base_types["list"] = list(base_types.values()) + [{**base_types}, None]
base_types["dict"] = {**base_types}


@pytest.mark.parametrize(
    "rows",
    [
        # Here we have 1 test per type for easy debugging
        *[[{k: v}] for k, v in base_types.items()],
        # Here we have 1 test for all the types
        [base_types],
        # Here is a nasty test with really hard unions
        [
            {"a": 1, "b": "hi", "c": TestType(2, "bye"), "i": image()},
            {"a": True, "b": True, "c": True, "i": True},
            {
                "a": [
                    1,
                    "hi",
                    True,
                    TestType(2, "bye"),
                    {"a": 1, "b": "hi", "c": TestType(2, "bye"), "i": image()},
                ]
            },
            {
                "randomly": {
                    "nested": {
                        "objects": {
                            "a": 1,
                            "b": "hi",
                            "c": TestType(2, "bye"),
                            "i": image(),
                        }
                    }
                }
            },
        ],
    ],
)
def test_row_batch(user_by_api_key_in_env, rows):
    do_batch_test(user_by_api_key_in_env.username, rows)


def compare_objects(a, b):
    if isinstance(a, Image.Image) and isinstance(b, Image.Image):
        return a.tobytes() == b.tobytes()
    elif isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(compare_objects(a_, b_) for a_, b_ in zip(a, b))
    elif isinstance(a, dict) and isinstance(b, dict):
        return len(a) == len(b) and all(
            k in b and compare_objects(a[k], b[k]) for k in a
        )
    return a == b


def make_optional_type(type_: weave.types.Type):
    if isinstance(type_, weave.types.List):
        type_ = weave.types.List(make_optional_type(type_.object_type))
    elif isinstance(type_, weave.types.TypedDict):
        type_ = weave.types.TypedDict(
            {k: make_optional_type(v) for k, v in type_.property_types.items()}
        )
    return weave.types.optional(type_)


def assert_type_assignment(a, b):
    if weave.types.optional(weave.types.TypedDict({})).assign_type(
        a
    ) and weave.types.optional(weave.types.TypedDict({})).assign_type(b):
        for k, ptype in a.property_types.items():
            assert k in b.property_types
            assert_type_assignment(ptype, b.property_types[k])
        return
    assert a.assign_type(b)


def do_batch_test(username, rows):
    table_name = "test_table_" + str(int(time.time()))
    st = wandb_stream_table.StreamTable(
        table_name=table_name, project_name="dev_test_weave_ci", entity_name=username
    )

    row_accumulator = []

    all_keys = set(["_step"])
    for row in rows:
        st.log(row)
        new_row = {
            "_step": len(row_accumulator),
            "_timestamp": datetime.datetime.now().timestamp(),
            **row,
        }
        row_accumulator.append(new_row)
        all_keys.update(list(row.keys()))

    row_type = weave.types.TypeRegistry.type_of([{}, *row_accumulator])
    run_node = weave.ops.project(
        st._lite_run._entity_name, st._lite_run._project_name
    ).run(st._lite_run._run_name)

    def do_assertion():
        history_node = run_node.history_stream()
        row_object_type = make_optional_type(row_type.object_type)

        for key in all_keys:
            column_node = history_node[key]
            assert_type_assignment(
                row_object_type.property_types[key], column_node.type.object_type
            )
            column_value = weave.use(column_node).to_pylist_tagged()
            expected = []

            # NOTICE: This is super weird b/c right now gorilla does not
            # give back rows that are missing keys. Once this fix is deployed
            # will need to update this test
            for row in row_accumulator:
                if key in row and row[key] is not None:
                    expected.append(row[key])
            assert compare_objects(column_value, expected)

    def history_is_uploaded():
        history_node = run_node.history_stream()
        run_data = get_raw_gorilla_history(
            st._lite_run._entity_name,
            st._lite_run._project_name,
            st._lite_run._run_name,
        )
        history = run_data.get("parquetHistory", {})
        return (
            len(history.get("liveData", []))
            == len(row_accumulator)
            == (run_data.get("historyKeys", {}).get("lastStep", -999) + 1)
            and history.get("parquetUrls") == []
            and len(row_type.object_type.property_types)
            == len(history_node.type.object_type.property_types)
        )

    # def history_is_compacted():
    #     history = get_raw_gorilla_history(
    #         run._entity_name, run._project_name, run._run_name
    #     )
    #     return history.get("liveData") == [] and len(history.get("parquetUrls", [])) > 0

    # First assertion is with liveset
    wait_for_x_times(history_is_uploaded)
    do_assertion()
    st.finish()

    # Second assertion is with parquet files
    # This is not supported
    # ensure_history_compaction_runs(run._entity_name, run._project_name, run._run_name)
    # wait_for_x_times(history_is_compacted)
    # do_assertion()


def wait_for_x_times(for_fn, times=10, wait=1):
    done = False
    while times > 0 and not done:
        times -= 1
        done = for_fn()
        time.sleep(wait)
    assert times > 0


def get_raw_gorilla_history(entity_name, project_name, run_name):
    query = """query WeavePythonCG($entityName: String!, $projectName: String!, $runName: String! ) {
            project(name: $projectName, entityName: $entityName) {
                run(name: $runName) {
                    historyKeys
                    parquetHistory(liveKeys: ["_timestamp"]) {
                        liveData
                        parquetUrls
                    }
                }
            }
    }"""
    variables = {
        "entityName": entity_name,
        "projectName": project_name,
        "runName": run_name,
    }
    res = wandb_gql_query(query, variables)
    return res.get("project", {}).get("run", {})


# Doesn't work yet
# def ensure_history_compaction_runs(entity_name, project_name, run_name):
#     client = wandb_public_api().client
#     # original_url = client._client.transport.url
#     # original_schema = client._client.schema
#     # client._client.transport.url = "http://localhost:8080/admin/parquet_workflow"

#     test_api_key = wandb_public_api().api_key

#     post_args = {
#         "headers": client._client.transport.headers,
#         "cookies": client._client.transport.cookies,
#         "auth": ("api", test_api_key),
#         "timeout": client._client.transport.default_timeout,
#         "data": {
#             "task_type": "export_history_to_parquet",
#             "run_key": {
#                 "entity_name": entity_name,
#                 "project_name": project_name,
#                 "run_name": run_name,
#             },
#         },
#     }
#     request = client._client.transport.session.post(
#         "http://localhost:8080/admin/parquet_workflow", **post_args
#     )

#     print(request)

#     client.execute()

#     # client._client.transport.url = original_url
#     # client._client.schema = original_schema
