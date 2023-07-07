import datetime
import time
import typing
import datetime

import pytest
import weave
from .. import context_state as _context
from PIL import Image
import numpy as np

# from weave.ops_domain.run_history.history_op_common import TypeCount
from weave.ops_domain.run_history.run_history_v3_parquet_weave_only import (
    _refine_history_type_inner,
)

from weave.wandb_interface.wandb_lite_run import InMemoryLazyLiteRun

from weave.wandb_client_api import wandb_gql_query, wandb_public_api
from weave.wandb_interface import wandb_stream_table


# def test_weave_type_decoding(user_by_api_key_in_env):
#     rows = [{"a": 1}]

#     run = InMemoryLazyLiteRun(project_name="dev_test_weave_ci")

#     total_rows = []
#     all_keys = set()
#     for row in rows:
#         run.log(row)
#         new_row = {
#             "_step": len(total_rows),
#             "_timestamp": datetime.datetime.now().timestamp(),
#             **row,
#         }
#         total_rows.append(new_row)
#         all_keys.update(list(row.keys()))
#     run.finish()

#     row_type = weave.types.TypeRegistry.type_of([{}, *total_rows])
#     run_node = weave.ops.project(run._entity_name, run._project_name).run(run._run_name)

#     history_node = run_node.history2()
#     assert row_type.assign_type(history_node.type)

#     for key in all_keys:
#         column_node = history_node[key]
#         column_value = weave.use(column_node).to_pylist_raw()
#         assert column_value == [row.get(key) for row in total_rows]


# def test_weave_history_decoding_snapshot():
#     from .history_decoding.logs import logs
#     from .history_decoding.history_keys import history_keys
#     from .history_decoding.live_data import live_data
#     from .history_decoding.weave_type import weave_type

#     type_parse = _refine_history_type_inner(history_keys["keys"])
#     w_type = weave.types.TypeRegistry.type_from_dict(weave_type)
#     w_object_type = weave.types.union(w_type.object_type, weave.types.TypedDict())
#     p_object_type = type_parse.weave_type

#     for key, val in p_object_type.property_types.items():
#         assert key in w_object_type.property_types
#         assert w_object_type.property_types[key].assign_type(val)


# from pyarrow import parquet as pq
# import dataclasses
# import json


# class SimpleTypeCount(typing.TypedDict):
#     type: typing.Literal["string", "number", "bool", "nil"]


# class CustomTypeCount(typing.TypedDict):
#     type: str
#     keys: dict[str, list["TypeCount"]]


# class MapTypeCount(typing.TypedDict):
#     type: typing.Literal["map"]
#     keys: dict[str, list["TypeCount"]]


# class ListTypeCount(typing.TypedDict):
#     type: typing.Literal["list"]
#     items: list["TypeCount"]


# TypeCount = typing.Union[SimpleTypeCount, CustomTypeCount, MapTypeCount, ListTypeCount]


# class MockedGorillaHistoryTypeCount(typing.TypedDict):
#     typeCounts: list[TypeCount]


# @dataclasses.dataclass
# class MockedGorillaHistory:
#     history_keys: dict[str, MockedGorillaHistoryTypeCount]
#     live_set_dict_rows: list[dict]
#     parquet_arrow_rows: typing.Any  # pq


# # def merge_typecount(a: TypeCount, b: TypeCount) -> list[TypeCount]:
# # if a['type'] != b['type']:
# #     return [a, b]
# # else:


# def typecount_of_val(val: typing.Any) -> TypeCount:
#     if isinstance(val, (int, float)):
#         return SimpleTypeCount(type="number")
#     elif isinstance(val, (str)):
#         return SimpleTypeCount(type="string")
#     elif isinstance(val, (bool)):
#         return SimpleTypeCount(type="bool")
#     elif val == None:
#         return SimpleTypeCount(type="nil")
#     elif isinstance(val, (list)):
#         types = {}
#         for item in val:
#             tc = typecount_of_val(item)
#             tc_typename = tc["type"]
#             if tc_typename not in types:
#                 types[tc_typename] = tc
#             elif "keys" in tc_typename:
#                 # merge keys
#                 pass
#         return ListTypeCount(type="list", items=list(types.values()))
#     elif isinstance(val, (dict)):
#         keys = {}
#         for key, item in val.items():
#             keys[key] = typecount_of_val(item)
#         if "_type" in val:
#             return CustomTypeCount(type=val["_type"], keys=keys)
#         else:
#             return MapTypeCount(type="map", keys=keys)
#     else:
#         raise Exception(f"Not supported: {type(val)}")


# def mock_gorilla_history(history_rows: list[dict]) -> MockedGorillaHistory:
#     # Step 1: apply flattening pre-processor
#     processed_rows = []
#     history_keys: dict[str, MockedGorillaHistoryTypeCount] = {}
#     for row in history_rows:
#         processed_row = {}
#         for key, val in row.items():
#             if not isinstance(val, dict) or "_type" in val:
#                 processed_row[key] = val
#             else:
#                 # flatten keys
#                 queue = [([key], val)]
#                 while queue:
#                     path, item = queue.pop()
#                     if not isinstance(item, dict) or "_type" in item:
#                         processed_row[".".join(path)] = item
#                     else:
#                         for subkey, subitem in item.items():
#                             queue.append(([*path, subkey], subitem))
#         processed_rows.append(processed_row)
#         # Handle the typing
#         history_keys_set: dict[str, set[str]] = {}
#         for key, val in processed_row.items():
#             if isinstance(val, dict) and "_type" not in val:
#                 raise Exception("Programming error")
#             if key not in history_keys_set:
#                 history_keys_set[key] = set()
#                 history_keys[key] = MockedGorillaHistoryTypeCount(typeCounts=[])
#             tc = typecount_of_val(val)
#             tc_id = json.dumps(tc)
#             if tc_id not in history_keys_set[key]:
#                 history_keys_set[key].add(tc_id)
#                 history_keys[key]["typeCounts"].append(tc)

#     split = int(len(processed_rows) / 5)
#     live_set_rows = processed_rows[:split]
#     parquet_rows = processed_rows[split:]

#     return MockedGorillaHistory(history_keys, live_set_rows, None)


# def test_history_mock():
#     res = mock_gorilla_history(
#         [
#             {
#                 "str": "hello_world",
#                 "int": 42,
#                 "float": 3.14,
#                 "bool": True,
#                 "list_of_int": [1, 2, 3],
#                 "list_of_mixed": ["a", 1, "b", 2, None, True],
#                 "dict_of_int": {"a": 1},
#                 "dict_of_mixed": {"a": 1, "b": "hi", "c": None},
#                 "list_of_dict": [{"a": 1}, {"a": 2}],
#                 "list_of_dict_mixed": [
#                     1,
#                     [1, {"a": 1}],
#                     {"a": {"b": {"_type": "thing", "nested": "other"}}},
#                     {"a": [{"b": {"c": [1]}}]},
#                     {"a": [{"b": {"c": [2]}, "d": 3}]},
#                     {"a": [{"b": {"c": "hi"}, "d": 3}]},
#                 ],
#                 "things_with_types": [{"_type": "thing", "nested": "other"}],
#             }
#         ]
#     )
#     assert res == None


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
        [{"a": TestType(1, "hi")}],
        [base_types],
        [
            {"a": 1, "b": "hi", "c": TestType(2, "bye"), "i": image()},
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
        return all(compare_objects(a_, b_) for a_, b_ in zip(a, b))
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

        # history_row_type = history_node.type.object_type
        row_object_type = make_optional_type(row_type.object_type)

        # Custom assign so we can debug easier
        # for k, ptype in row_object_type.property_types.items():
        #     if isinstance(ptype, weave.types.NoneType) or k in ["_step", "_timestamp"]:
        #         continue
        #     assert k in history_row_type.property_types
        #     assert_type_assignment(ptype, history_row_type.property_types[k])

        for key in all_keys:
            column_node = history_node[key]
            assert_type_assignment(
                row_object_type.property_types[key], column_node.type.object_type
            )
            column_value = weave.use(column_node).to_pylist_tagged()
            assert compare_objects(
                column_value, [row.get(key) for row in row_accumulator]
            )

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


# def test_history_logging(user_by_api_key_in_env):
#     rows = [{"a": 1}]
#     run = InMemoryLazyLiteRun(project_name="dev_test_weave_ci")

#     total_rows = []

#     all_keys = set()
#     for row in rows:
#         run.log(row)
#         new_row = {
#             "_step": len(total_rows),
#             "_timestamp": datetime.datetime.now().timestamp(),
#             **row,
#         }
#         total_rows.append(new_row)
#         all_keys.update(list(row.keys()))

#     row_type = weave.types.TypeRegistry.type_of([{}, *total_rows])
#     run_node = weave.ops.project(run._entity_name, run._project_name).run(run._run_name)

#     def do_assertion():
#         history_node = run_node.history2()
#         assert row_type.assign_type(history_node.type)

#         for key in all_keys:
#             column_node = history_node[key]
#             column_value = weave.use(column_node).to_pylist_raw()
#             assert column_value == [row.get(key) for row in total_rows]

#     def history_is_uploaded():
#         history = get_raw_gorilla_history(
#             run._entity_name, run._project_name, run._run_name
#         )
#         return (
#             len(history.get("liveData", [])) == len(total_rows)
#             and history.get("parquetUrls") == []
#         )

#     def history_is_compacted():
#         history = get_raw_gorilla_history(
#             run._entity_name, run._project_name, run._run_name
#         )
#         return history.get("liveData") == [] and len(history.get("parquetUrls", [])) > 0

#     # First assertion is with liveset
#     wait_for_x_times(history_is_uploaded)
#     do_assertion()

#     # Second assertion is with parquet files
#     run.finish()
#     # This is not supported
#     # ensure_history_compaction_runs(run._entity_name, run._project_name, run._run_name)
#     wait_for_x_times(history_is_compacted)
#     do_assertion()


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


def ensure_history_compaction_runs(entity_name, project_name, run_name):
    client = wandb_public_api().client
    # original_url = client._client.transport.url
    # original_schema = client._client.schema
    # client._client.transport.url = "http://localhost:8080/admin/parquet_workflow"

    test_api_key = wandb_public_api().api_key

    post_args = {
        "headers": client._client.transport.headers,
        "cookies": client._client.transport.cookies,
        "auth": ("api", test_api_key),
        "timeout": client._client.transport.default_timeout,
        "data": {
            "task_type": "export_history_to_parquet",
            "run_key": {
                "entity_name": entity_name,
                "project_name": project_name,
                "run_name": run_name,
            },
        },
    }
    request = client._client.transport.session.post(
        "http://localhost:8080/admin/parquet_workflow", **post_args
    )

    print(request)

    client.execute()

    # client._client.transport.url = original_url
    # client._client.schema = original_schema
