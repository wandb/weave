import datetime
import json
import os
import time

import numpy as np
import pytest
from PIL import Image

import weave
from weave.legacy.weave import context_state as _context
from weave.legacy.weave.ops_domain.run_history.context import (
    error_on_non_vectorized_history_transform,
)
from weave.legacy.weave.ops_domain.run_history.history_op_common import _without_tags
from weave.legacy.weave.wandb_client_api import wandb_gql_query
from weave.legacy.weave.wandb_interface import wandb_stream_table

HISTORY_OP_NAME = "history3"


def image():
    imarray = np.random.rand(100, 100, 3) * 255
    return Image.fromarray(imarray.astype("uint8")).convert("RGBA")


_loading_builtins_token = _context.set_loading_built_ins()


@weave.type()
class CustomHistoryTestType:
    a: int
    b: str


_context.clear_loading_built_ins(_loading_builtins_token)


def make_base_types():
    return {
        "number": 42,
        "string": "hello world",
        "boolean": True,
        "object": CustomHistoryTestType(1, "hi"),
        "custom": image(),
        "user_defined_timestamp": datetime.datetime.now(),
    }


def make_all_types():
    base_types = make_base_types()
    base_types["list"] = list(make_base_types().values()) + [
        {**make_base_types()},
        None,
    ]
    base_types["dict"] = {**make_base_types()}
    return base_types


rows_tests = [
    # Here we have 1 test per type for easy debugging
    *[[{k: v}] for k, v in make_all_types().items()],
    # # Here we have 1 test for all the types
    [make_all_types()],
    # Here is a nasty test with really hard unions
    [{"list_of": [1, 2, 3]}, {"list_of": [4, 5]}],
    [
        {
            "a": image(),
        },
        {
            "a": 1,
        },
    ],
    [{"list_of_image": [image()]}],
    [
        {"a": [{"b": [1]}, {"b": [2, 3]}]},
        {"a": [{"b": [4, 5, 6]}, {"b": [7, 8, 9, 10]}]},
    ],
    [
        {"a": 1, "b": "hi", "c": CustomHistoryTestType(2, "bye"), "i": image()},
        {"a": True, "b": True, "c": True, "i": True},
        {
            "a": [
                1,
                "hi",
                True,
                CustomHistoryTestType(2, "bye"),
                {"a": 1, "b": "hi", "c": CustomHistoryTestType(2, "bye"), "i": image()},
            ]
        },
        {
            "randomly": {
                "nested": {
                    "objects": {
                        "a": 1,
                        "b": "hi",
                        "c": CustomHistoryTestType(2, "bye"),
                        "i": image(),
                    }
                }
            }
        },
    ],
]


@pytest.mark.parametrize(
    "rows",
    rows_tests,
)
def test_end_to_end_stream_table_history_path_batch_1(user_by_api_key_in_env, rows):
    return do_test_end_to_end_stream_table_history_path(
        user_by_api_key_in_env.username, rows
    )


def do_test_end_to_end_stream_table_history_path(username, rows):
    def do_assertion(history_node, row_type, row_accumulator, user_logged_keys):
        row_object_type = make_optional_type(row_type.object_type)

        for key in user_logged_keys:
            column_node = history_node[key]
            assert_type_assignment(
                row_object_type.property_types[key], column_node.type.object_type
            )
            column_value = weave.use(column_node).to_pylist_tagged()
            expected = []

            for row in row_accumulator:
                expected.append(row.get(key))
            assert compare_objects(column_value, expected)

    do_batch_test(username, rows, do_assertion)


def test_nested_pick_via_dots(user_by_api_key_in_env):
    rows = [
        {
            "a": 1,
            "b": {
                "c": 2,
            },
            "d.e": 3,
        }
    ]

    def do_assertion(history_node, row_type, row_accumulator, user_logged_keys):
        with error_on_non_vectorized_history_transform():
            assert weave.use(history_node["a"]).to_pylist_tagged() == [1]
            assert weave.use(history_node["b"]).to_pylist_tagged() == [{"c": 2}]
            assert weave.use(history_node["b"]["c"]).to_pylist_tagged() == [2]
            assert weave.use(history_node["b.c"]).to_pylist_tagged() == [2]
            assert weave.use(history_node["d"]).to_pylist_tagged() == [{"e": 3}]
            assert weave.use(history_node["d.e"]).to_pylist_tagged() == [3]

    do_batch_test(user_by_api_key_in_env.username, rows, do_assertion)


def test_missing_data(user_by_api_key_in_env):
    rows = [{"a": "1", "b": "17", "c": "42"}, {"a": "2"}]

    def do_assertion(history_node, row_type, row_accumulator, user_logged_keys):
        nodes = [
            history_node[0]["a"],
            history_node[0]["b"],
            history_node[1]["a"],
            history_node[1]["b"],
        ]
        res = weave.use(nodes)
        assert res[0] == "1"
        assert res[1] == "17"
        assert res[2] == "2"
        assert res[3] == None

    do_batch_test(user_by_api_key_in_env.username, rows, do_assertion)


def do_batch_test(username, rows, do_assertion):
    row_accumulator, st, user_logged_keys = do_logging(username, rows)

    row_type = weave.types.TypeRegistry.type_of([{}, *row_accumulator])
    run_node = weave.legacy.weave.ops.project(st._entity_name, st._project_name).run(
        st._table_name
    )

    # First assertion is with liveset
    wait_for_x_times(
        lambda: history_is_uploaded(
            run_node,
            len(row_accumulator),
            len(row_type.object_type.property_types),
            st._entity_name,
            st._project_name,
            st._table_name,
        )
    )
    # Wait for files to be uploaded
    st._flush()
    wait_for_x_times(lambda: st._lite_run.pusher._incoming_queue.empty())
    wait_for_x_times(lambda: st._lite_run.pusher._event_queue.empty())
    wait_for_x_times(lambda: st._lite_run.stream._queue.empty())
    history_node = run_node._get_op(HISTORY_OP_NAME)()
    do_assertion(history_node, row_type, row_accumulator, user_logged_keys)
    st.finish()

    if os.environ.get("PARQUET_ENABLED"):
        # Second assertion is with parquet files
        wait_for_x_times(
            lambda: history_moved_to_parquet(
                st._entity_name,
                st._project_name,
                st._table_name,
            )
        )
        history_node = run_node._get_op(HISTORY_OP_NAME)()
        do_assertion(history_node, row_type, row_accumulator, user_logged_keys)


def do_logging(username, rows, finish=False):
    table_name = "test_table_" + str(int(time.time()))
    st = wandb_stream_table.StreamTable(
        table_name=table_name,
        project_name="dev_test_weave_ci",
        entity_name=username,
        _disable_async_file_stream=True,
    )

    row_accumulator = []

    all_keys = set(["_step"])
    for row in rows:
        st.log(row)
        new_row = {
            # Extra fields automatically added from the Run
            "_step": len(row_accumulator),
            "_timestamp": datetime.datetime.now().timestamp(),
            # Extra fields automatically added from the StreamTable
            "_client_id": "dummy",
            "timestamp": datetime.datetime.utcnow(),
            # User fields
            **row,
        }
        row_accumulator.append(new_row)
        all_keys.update(list(row.keys()))

    if finish:
        st.finish()

    return row_accumulator, st, all_keys


def history_is_uploaded(
    run_node, exp_len, exp_cols_len, entity_name, project_name, run_name
):
    history_node = run_node._get_op(HISTORY_OP_NAME)()
    run_data = get_raw_gorilla_history(
        entity_name,
        project_name,
        run_name,
    )
    history = run_data.get("parquetHistory", {})
    return (
        len(history.get("liveData", []))
        == exp_len
        == (run_data.get("historyKeys", {}).get("lastStep", -999) + 1)
        and history.get("parquetUrls") == []
        and exp_cols_len == len(history_node.type.object_type.property_types)
    )


def history_moved_to_parquet(entity_name, project_name, run_name):
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
    elif isinstance(a, datetime.datetime) and isinstance(b, datetime.datetime):
        return int(a.timestamp() * 1000) == int(b.timestamp() * 1000)
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
    a = _without_tags(a)
    b = _without_tags(b)
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


@pytest.mark.skip(reason="Local Perf Testing")
@pytest.mark.parametrize(
    "n_rows, n_cols",
    [
        # (100, 100),
        (1500, 1500),
        (10_000, 1_000),
        (1_000_000, 1_000),
        (1_000_000, 10_000),
        (10_000_000, 10_000),
    ],
)
def test_stream_table_perf(user_by_api_key_in_env, n_rows, n_cols):
    print(f"Conducting StreamTable perf test using {n_rows} rows and {n_cols} cols")
    table_name = "test_table_" + str(int(time.time()))
    st = wandb_stream_table.StreamTable(
        table_name=table_name,
        project_name="dev_test_weave_ci",
        entity_name=user_by_api_key_in_env.username,
        _disable_async_file_stream=True,
    )
    timings = {
        "log": 0,
        "history2_refine": 0,
        "history2_fetch_100_cols": 0,
        "history3_refine": 0,
        "history3_fetch_100_cols": 0,
    }
    print_interval = int(n_rows / 10)
    timings["log"] = 0
    for i in range(n_rows):
        row = {}
        for j in range(n_cols):
            row[f"col_{j}"] = (i * j) + (i + j)
        timings["log"] -= time.time()
        st.log(row)
        timings["log"] += time.time()
        if i % print_interval == 0:
            print(f"Logged {i} rows")
        if i % 100 == 0:
            time.sleep(0.5)

    print("Finishing Run")
    timings["log"] -= time.time()
    st.finish()
    timings["log"] += time.time()
    print(f"Log Time: {timings['log']}")

    run_node = weave.legacy.weave.ops.project(st._entity_name, st._project_name).run(
        st._table_name
    )

    timings["history2_refine"] -= time.time()
    history2_node = run_node.history2()
    timings["history2_refine"] += time.time()
    print(f"History2 Refine Time: {timings['history2_refine']}")

    fetch_nodes = [history2_node[f"col_{i}"] for i in range(100)]
    timings["history2_fetch_100_cols"] -= time.time()
    res = weave.use(fetch_nodes)
    timings["history2_fetch_100_cols"] += time.time()
    print(f"History2 Fetch 100 Cols Time: {timings['history2_fetch_100_cols']}")

    timings["history3_refine"] -= time.time()
    history3_node = run_node.history3()
    timings["history3_refine"] += time.time()
    print(f"History Stream Refine Time: {timings['history3_refine']}")

    fetch_nodes = [history3_node[f"col_{i}"] for i in range(100)]
    timings["history3_fetch_100_cols"] -= time.time()
    res = weave.use(fetch_nodes)
    timings["history3_fetch_100_cols"] += time.time()
    print(f"History Stream Fetch 100 Cols Time: {timings['history3_fetch_100_cols']}")

    print(f"Perf for {n_rows} rows and {n_cols} cols:")
    print(json.dumps(timings, indent=2))
    assert timings == None
