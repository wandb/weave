import shutil
from . import api as weave
from . import graph
from . import storage
from .artifacts_local import LOCAL_ARTIFACT_DIR

from .weave_internal import make_const_node


def test_node_expr():
    nine = make_const_node(weave.types.Number(), 9)
    res = (nine + 3) * 4
    assert weave.use(res) == 48
    exp = graph.node_expr_str(res)
    # TODO: make node_expr_str use binary ops (make match frontend
    # impl)
    assert exp == "add(9, 3).mult(4)"


# def test_value_expr():
#     nine = make_const_node(weave.types.Number(), 9)
#     res = weave.use((nine + 3) * 4)
#     exp = storage.get_obj_expr(res)
#     assert exp == "add(9, 3).mult(4)"


def test_versions():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass

    nine = make_const_node(weave.types.Number(), 9)
    weave.use(weave.save((nine + 3) * 4, name="my-obj"))
    res = weave.use(weave.save((nine + 6) * 4, name="my-obj"))
    assert res == 60
    versions = weave.versions(res)
    version_exprs = [str(weave.expr(v)) for v in versions]
    assert version_exprs == [
        'add(9, 3).mult(4).save("my-obj")',
        'add(9, 6).mult(4).save("my-obj")',
    ]
