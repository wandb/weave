import typing
import weave
from .. import api
from .. import weave_types as types
from .. import weave_internal
from .. import ops
from .. import execute
from .. import environment
from . import test_wb
import pytest

execute_test_count_op_run_count = 0


@api.op(input_type={"x": types.Any()}, output_type=types.Number())
def execute_test_count_op(x):
    global execute_test_count_op_run_count
    execute_test_count_op_run_count += 1
    return len(x)


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
    assert res == [12]


REFINE_CALLED = 0


@weave.op()
def _test_execute_refining_op_refine(x: int) -> weave.types.Type:
    global REFINE_CALLED
    REFINE_CALLED += 1
    return weave.types.Int()


@weave.op(refine_output_type=_test_execute_refining_op_refine)
def _test_execute_refining_op(x: int) -> typing.Any:
    return x + 1


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
    fake_wandb.add_mock(test_wb.table_mock1)
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
    assert stats["node_count"] == 15
