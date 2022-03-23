from . import api
from . import weave_types as types
from . import ops

execute_test_count_op_run_count = 0


@api.op(input_type={"x": types.Any()}, output_type=types.Number())
def execute_test_count_op(x):
    global execute_test_count_op_run_count
    execute_test_count_op_run_count += 1
    return len(x.list)


def test_local_file_pure_cached():
    # local_path() is impure, but the operations thereafter are pure
    # this test confirms that pure ops that come after impure ops hit cache
    import shutil

    try:
        shutil.rmtree("local-artifacts")
    except FileNotFoundError:
        pass
    shutil.copy("testdata/cereal.csv", "/tmp/cereal.csv")

    global execute_test_count_op_run_count
    execute_test_count_op_run_count = 0
    # We should only execute execute_test_count_op once.
    count1 = api.use(execute_test_count_op(ops.local_path("/tmp/cereal.csv").readcsv()))
    count2 = api.use(execute_test_count_op(ops.local_path("/tmp/cereal.csv").readcsv()))
    assert count1 == count2
    assert execute_test_count_op_run_count == 1
