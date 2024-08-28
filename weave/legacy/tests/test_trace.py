import re

from weave.legacy.weave import api as weave
from weave.legacy.weave import graph, storage
from weave.legacy.weave.weave_internal import make_const_node

from ...legacy.weave import trace_legacy


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


def test_trace():
    nine = make_const_node(weave.types.Number(), 9)
    res = weave.use((nine + 3) * 4)
    assert res == 48
    mult_run = trace_legacy.get_obj_creator(storage._get_ref(res))
    assert mult_run.op_name == "number-mult"
    assert re.match(
        "^local-artifact://.*run-number-add-.*-output:.*$", str(mult_run.inputs["lhs"])
    )
    assert mult_run.inputs["rhs"] == 4
    add_run = trace_legacy.get_obj_creator(mult_run.inputs["lhs"])
    assert add_run.op_name == "number-add"
    assert add_run.inputs == {"lhs": 9, "rhs": 3}
