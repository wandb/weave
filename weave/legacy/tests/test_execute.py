import os
import typing

import pytest

import weave
from weave.legacy.weave import api, environment, execute, ops, weave_internal
from weave.legacy.weave import weave_types as types

from . import test_wb

execute_test_count_op_run_count = 0

from weave.legacy.weave import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()


@api.op(input_type={"x": types.Any()}, output_type=types.Number(), hidden=True)
def execute_test_count_op(x):
    global execute_test_count_op_run_count
    execute_test_count_op_run_count += 1
    return len(x)


REFINE_CALLED = 0


@weave.op()
def _test_execute_refining_op_refine(x: int) -> weave.types.Type:
    global REFINE_CALLED
    REFINE_CALLED += 1
    return weave.types.Int()


@weave.op(refine_output_type=_test_execute_refining_op_refine)
def _test_execute_refining_op(x: int) -> typing.Any:
    return x + 1


_context_state.clear_loading_built_ins(_loading_builtins_token)


def test_local_file_pure_cached(cereal_csv):
    # local_path() is impure, but the operations thereafter are pure
    # this test confirms that pure ops that come after impure ops hit cache
    global execute_test_count_op_run_count
    execute_test_count_op_run_count = 0
    # We should only execute execute_test_count_op once.
    count1 = api.use(execute_test_count_op(ops.local_path(cereal_csv).readcsv()))
    count2 = api.use(execute_test_count_op(ops.local_path(cereal_csv).readcsv()))
    assert count1 == count2
    assert execute_test_count_op_run_count == 1


def test_execute_no_cache():
    nine = weave_internal.make_const_node(types.Number(), 9)
    res = execute.execute_nodes([nine + 3], no_cache=True)
    assert res.unwrap() == [12]


@pytest.fixture()
def weave_cache_mode_minimal():
    orig_cache_mode = environment.cache_mode

    def _cache_mode():
        return environment.CacheMode.MINIMAL

    environment.cache_mode = _cache_mode
    yield
    environment.cache_mode = orig_cache_mode


def test_execute_cache_mode_minimal_no_recursive_refinement(weave_cache_mode_minimal):
    called_once = _test_execute_refining_op(1)
    assert REFINE_CALLED == 1
    assert called_once.type == weave.types.Int()
    called_twice = _test_execute_refining_op(called_once)
    # with cache mode minimal, we do get recursive refine while construct
    # graphs by calling ops!
    assert REFINE_CALLED == 3
    assert called_twice.type == weave.types.Int()

    result = weave.use(called_twice)
    assert result == 3
    # But, when we execute with cache mode minimal, we only call each refine
    # once.
    assert REFINE_CALLED == 5


def test_we_dont_over_execute(fake_wandb):
    fake_wandb.fake_api.add_mock(test_wb.table_mock1)
    cell_node = (
        ops.project("stacey", "mendeleev")
        .runs()
        .limit(1)
        .summary()["table"]
        .table()
        .rows()
        .dropna()
        .concat()
        .createIndexCheckpointTag()[5]["score_Amphibia"]
    )
    with execute.top_level_stats() as stats:
        assert weave.use(cell_node.indexCheckpoint()) == 5

    # If this check fails, please be very careful! It means that something
    # has changed in the engine that is causing us to over-execute nodes
    # and is an indication of a serious performance regression.
    summary = stats.summary()
    assert summary["count"] - summary["already_executed"] == 16


def table_mock_respecting_run_name(q, ndx):
    # this is a more realistic gql responder that will only return run displayName
    # if its selected.
    if q["gql"].definitions[0].name.value == "WeavePythonCG":
        # is project.runs.edges.node.displayName selected?
        project_field = q["gql"].definitions[0].selection_set.selections[0]
        assert project_field.name.value == "project"
        runs_field = project_field.selection_set.selections[2]
        assert runs_field.name.value == "runs"
        runs_node = runs_field.selection_set.selections[0].selection_set.selections[0]
        node_fields = runs_node.selection_set.selections
        display_name_selected = any(f.name.value == "displayName" for f in node_fields)

        if display_name_selected:
            return test_wb.workspace_response()
        else:
            return test_wb.workspace_response_no_run_displayname
    else:
        return test_wb.artifact_version_sdk_response


def test_outer_tags_propagate_on_cache_hit(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock_respecting_run_name)
    row = (
        ops.project("stacey", "mendeleev")
        .runs()
        .limit(50)
        .summary()
        .pick("table")
        .offset(0)
        .limit(2)[0]
        .table()
        .rows()
        .createIndexCheckpointTag()[0]
    )
    # The first query does not select run.displayName, but it caches
    # results along the way.
    weave.use(row)

    # The cached results include tags that have gql results (which don't
    # include displayName since it wasn't selected in the prior query).

    # Now select displayName in a new query. This query will hit cache.
    # But we should get the correct result because we propagate outer
    # tags even on cache hits.
    run_names_res = weave.use(row.run().name())
    assert run_names_res == "amber-glade-100"


@weave.op()
def expensive_op(x: int) -> int:
    return x + 10000


@pytest.mark.skip(reason="Disabled in favor of parallelism for the moment.")
def test_cache_column():
    os.environ["WEAVE_CACHE_MODE"] = "minimal"

    input_vals = list(range(10))
    expected_result = [{"x": x, "y": x + 10000} for x in input_vals]

    l = weave.save(input_vals)
    mapped = l.map(lambda x: weave.legacy.weave.ops.dict_(x=x, y=expensive_op(x)))
    res = weave.use(mapped)
    assert res == expected_result

    latest_obj = weave.use(
        weave.legacy.weave.ops.get("local-artifact:///run-op-expensive_op:latest/obj")
    )
    assert len(latest_obj) == len(input_vals)
    assert len(weave.versions(latest_obj)) == 1


@pytest.mark.skip("was used for table caching which is disabled")
def test_none_not_cached():
    os.environ["WEAVE_CACHE_MODE"] = "minimal"

    input_vals = [1, None]
    expected_result = [10001, None]

    l = weave.save(input_vals)
    mapped = l.map(lambda x: expensive_op(x))
    res = weave.use(mapped)
    assert res == expected_result

    latest_obj = weave.use(
        weave.legacy.weave.ops.get("local-artifact:///run-op-expensive_op:latest/obj")
    )
    assert len(latest_obj) == 1  # not 2! None not cached!
    assert len(weave.versions(latest_obj)) == 1
