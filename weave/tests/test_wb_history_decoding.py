import datetime
import os
import time
import datetime

import pytest
import weave
from weave.ops_domain.run_history import run_history_v3_parquet_weave_only
from weave.ops_domain.run_history import history_op_common
from .. import context_state as _context
from PIL import Image
import numpy as np

import requests
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

rows_tests = [
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
]


@pytest.mark.parametrize(
    "rows, mocked_parquet_file_path",
    [
        (rows, f"./test_parquet_files/test_{test_ndx}.parquet")
        for test_ndx, rows in enumerate(rows_tests)
    ],
)
def test_row_batch(user_by_api_key_in_env, rows, mocked_parquet_file_path):
    do_batch_test(user_by_api_key_in_env.username, rows, mocked_parquet_file_path)


# Uncomment this skip test and run it with a locally authenticated machine
# to generate local parquet files for testing
@pytest.mark.skip(reason="local test for generating parquet files")
def test_make_parquet_files():
    for test_ndx, rows in enumerate(rows_tests):
        row_accumulator, st, all_keys = do_logging("timssweeney", rows, finish=True)
        wait_for_x_times(
            lambda: history_is_compacted(
                st._lite_run._entity_name,
                st._lite_run._project_name,
                st._lite_run._run_name,
            )
        )
        run = get_raw_gorilla_history(
            st._lite_run._entity_name,
            st._lite_run._project_name,
            st._lite_run._run_name,
        )
        r = requests.get(run["parquetHistory"]["parquetUrls"][0], allow_redirects=True)
        os.makedirs("test_parquet_files", exist_ok=True)
        open(f"test_parquet_files/test_{test_ndx}.parquet", "wb").write(r.content)


def do_logging(username, rows, finish=False):
    table_name = "test_table_" + str(int(time.time()))
    st = wandb_stream_table.StreamTable(
        table_name=table_name,
        project_name="dev_test_weave_ci",
        entity_name=username,
        _disable_async_logging=True,
    )

    row_accumulator = []

    all_keys = set(["_step"])
    for row in rows:
        st.log(row)
        new_row = {
            # Need to simulate the extra fields that the logger a
            "_step": len(row_accumulator),
            "_timestamp": datetime.datetime.now().timestamp(),
            "_client_id": "dummy",
            "timestamp": datetime.datetime.utcnow(),
            **row,
        }
        row_accumulator.append(new_row)
        all_keys.update(list(row.keys()))

    if finish:
        st.finish()

    return row_accumulator, st, all_keys


# // I think data is screwed up on #6...
# TODO:
# I think we need to correct the nesting still...
# replace _type/_val with _val contents
#


def do_batch_test(username, rows, mocked_parquet_file_path):
    row_accumulator, st, all_keys = do_logging(username, rows)

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

        # For now we have to mock the parquet file bit (until gorilla has parquet in local)
        # Once the local backend supports compaction, we can remove this whole bit, the mocked
        # parquet files, etc... And just do the second assertion pass at the end of this function.
        history_row_type = history_node.type.object_type.value
        history_awl = run_history_v3_parquet_weave_only._get_history_stream_inner(
            run_history_v3_parquet_weave_only.HistoryToWeaveFinalResult(
                history_row_type, []
            ),
            live_data=[],
            parquet_history=history_op_common.process_history_awl_tables(
                [
                    history_op_common.local_path_to_parquet_table(
                        path=mocked_parquet_file_path,
                        object_type=None,
                        columns=list(history_row_type.property_types.keys()),
                    )
                ]
            ),
        )
        history_results = history_awl.to_pylist_tagged()
        for key in all_keys:
            # NOTICE: This is super weird b/c right now gorilla does not
            # give back rows that are missing keys. Once this fix is deployed
            # will need to update this test
            expected = []
            for row in row_accumulator:
                if key in row and row[key] is not None:
                    expected.append(row[key])

            found = []
            for row in history_results:
                found.append(row[key])

            assert compare_objects(found, expected)

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

    # First assertion is with liveset
    wait_for_x_times(history_is_uploaded)
    do_assertion()
    st.finish()

    # Second assertion is with parquet files
    # This is not supported
    # ensure_history_compaction_runs(run._entity_name, run._project_name, run._run_name)
    # wait_for_x_times(lambda: history_is_compacted(run._entity_name, run._project_name, run._run_name))
    # do_assertion()


def history_is_compacted(entity_name, project_name, run_name):
    history = get_raw_gorilla_history(entity_name, project_name, run_name)
    return (
        history.get("parquetHistory", {}).get("liveData") == []
        and len(history.get("parquetHistory", {}).get("parquetUrls", [])) > 0
    )


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
