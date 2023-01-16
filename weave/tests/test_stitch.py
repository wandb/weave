import weave
import typing
import pytest

from weave import serialize

from .. import stitch

from ..language_features.tagging import make_tag_getter_op
from .. import compile_table
from weave import context_state as _context

from weave import weave_internal

_loading_builtins_token = _context.set_loading_built_ins()


@weave.type()
class _TestPlanObject:
    _name: str
    val: int

    # Because this is named "Test*", doing .name() will tag the result
    @weave.op()
    def name(self) -> str:
        return self._name


@weave.op()
def dummy_no_arg_op() -> typing.List[_TestPlanObject]:
    return [_TestPlanObject("x", 1)]


@weave.type()
class _TestPlanHasObject:
    name: str
    _obj: _TestPlanObject


# Because this is named "Test*", doing .name() will tag the result
@weave.op()
def _test_hasobj_obj(self_has_obj: _TestPlanHasObject) -> _TestPlanObject:
    return self_has_obj._obj


get_object_self_tag = make_tag_getter_op.make_tag_getter_op("self", _TestPlanObject.WeaveType())  # type: ignore
get_hasobject_self_tag = make_tag_getter_op.make_tag_getter_op("self_has_obj", _TestPlanHasObject.WeaveType())  # type: ignore

_context.clear_loading_built_ins(_loading_builtins_token)


def test_traverse_tags():
    obj_node = weave.save(_TestPlanObject("a", 1))
    obj_from_tag_val_node = get_object_self_tag(obj_node.name() + "hello").val
    p = stitch.stitch([obj_from_tag_val_node])
    obj_recorder = p.get_result(obj_node)
    assert len(obj_recorder.calls) == 2
    assert obj_recorder.calls[0].node.from_op.name == "_TestPlanObject-name"
    assert obj_recorder.calls[1].node.from_op.name == "Object-__getattr__"
    assert obj_recorder.calls[1].inputs[1].val == "val"


def test_traverse_tags_2level():
    obj_node = weave.save(_TestPlanHasObject("has", _TestPlanObject("a", 1)))
    name_add_node = obj_node._test_hasobj_obj().name() + "hello"
    obj_from_tag_val_node = get_hasobject_self_tag(
        get_object_self_tag(name_add_node)
    ).name
    p = stitch.stitch([obj_from_tag_val_node])
    obj_recorder = p.get_result(obj_node)
    assert len(obj_recorder.calls) == 2
    assert obj_recorder.calls[0].node.from_op.name == "op-_test_hasobj_obj"
    assert obj_recorder.calls[1].node.from_op.name == "Object-__getattr__"
    assert obj_recorder.calls[1].inputs[1].val == "name"


def test_enter_filter():
    objs_node = weave.save([{"a": 5, "b": 6, "c": 10}, {"a": 7, "b": 8, "c": 11}])
    p = stitch.stitch([objs_node["b"], objs_node.filter(lambda obj: obj["a"] > 6)])
    obj_recorder = p.get_result(objs_node)
    calls = obj_recorder.calls
    assert len(calls) == 2
    assert calls[0].node.from_op.name == "mapped_typedDict-pick"
    assert calls[0].inputs[1].val == "b"
    assert calls[1].node.from_op.name == "typedDict-pick"
    assert calls[1].inputs[1].val == "a"


def test_lambda_using_externally_defined_node():
    objs_node = weave.save([{"a": 5, "b": 6, "c": 10}, {"a": 7, "b": 8, "c": 11}])
    # Inside the lambda, we use externally defined `objs_node`. This should
    # result in all 3 calls being recorded
    p = stitch.stitch(
        [objs_node["b"], objs_node.filter(lambda obj: obj["a"] > objs_node[0]["b"])]
    )
    obj_recorder = p.get_result(objs_node)
    calls = obj_recorder.calls
    assert len(calls) == 3
    assert calls[0].node.from_op.name == "mapped_typedDict-pick"
    assert calls[0].inputs[1].val == "b"
    assert calls[1].node.from_op.name == "list-__getitem__"
    assert calls[1].inputs[1].val == 0
    assert calls[2].node.from_op.name == "typedDict-pick"
    assert calls[2].inputs[1].val == "a"


def test_tag_access_in_filter_expr():
    objs_node = weave.save([_TestPlanObject("a", 1), _TestPlanObject("b", 2)])
    leaf = objs_node.name().filter(lambda obj: get_object_self_tag(obj).val > 2)
    p = stitch.stitch([leaf])
    obj_recorder = p.get_result(objs_node)
    calls = obj_recorder.calls
    assert len(calls) == 2
    assert calls[0].node.from_op.name == "mapped__TestPlanObject-name"
    assert calls[1].node.from_op.name == "Object-__getattr__"
    assert calls[1].inputs[1].val == "val"


def test_travese_dict():
    obj_node = weave.save(_TestPlanObject("a", 1))
    p = stitch.stitch([weave.ops.dict_(x=obj_node)["x"].name()])
    obj_recorder = p.get_result(obj_node)
    assert len(obj_recorder.calls) == 1
    assert obj_recorder.calls[0].node.from_op.name == "_TestPlanObject-name"


def test_travese_groupby_dict():
    obj_node = weave.save([{"o": {"a": 5}, "x": 1}])
    grouped = obj_node.groupby(lambda row: weave.ops.dict_(x=row["o"]))
    output = grouped[0]["x"]
    grouped_x_o = grouped[0].groupkey()["x"]
    groupkey_output = grouped_x_o["a"]
    p = stitch.stitch([output, groupkey_output])
    obj_recorder = p.get_result(obj_node)

    assert compile_table.get_projection(obj_recorder) == {"o": {"a": {}}, "x": {}}


def test_zero_arg_ops():
    node = dummy_no_arg_op()
    p = stitch.stitch([node])
    obj_recorder = p.get_result(node)
    assert obj_recorder.calls == []

    p = stitch.stitch([node.name()])
    obj_recorder = p.get_result(node)
    assert len(obj_recorder.calls) == 1
    assert obj_recorder.calls[0].node.from_op.name == "mapped__TestPlanObject-name"

    p = stitch.stitch([node.filter(lambda x: x._get_op("name")() != "")])
    obj_recorder = p.get_result(node)
    assert len(obj_recorder.calls) == 1
    assert obj_recorder.calls[0].node.from_op.name == "_TestPlanObject-name"

    p = stitch.stitch([node.filter(lambda x: x._get_op("name")() != ""), node.name()])
    obj_recorder = p.get_result(node)
    assert len(obj_recorder.calls) == 2
    assert obj_recorder.calls[0].node.from_op.name == "_TestPlanObject-name"
    assert obj_recorder.calls[1].node.from_op.name == "mapped__TestPlanObject-name"


def test_shared_fn_node():
    const_list_node = weave.ops.make_list(a=1, b=2)
    indexed_node = const_list_node[0]
    fn_node = weave_internal.define_fn(
        {"row": weave.types.Number()},
        lambda row: weave.ops.dict_(item=row, const=indexed_node),
    )
    arr_1_node = weave.ops.make_list(a=1, b=2, c=3)
    arr_2_node = weave.ops.make_list(a=10, b=20, c=30)

    mapped_1_node = arr_1_node.map(fn_node)
    mapped_2_node = arr_2_node.map(fn_node)

    mapped_1_item_node = mapped_1_node["item"]
    mapped_1_const_node = mapped_1_node["const"]
    mapped_2_item_node = mapped_2_node["item"]
    mapped_2_const_node = mapped_2_node["const"]

    mapped_2_item_add_node = mapped_2_item_node + 100
    mapped_2_const_add_node = mapped_2_const_node + 100

    list_of_list_node = weave.ops.make_list(
        a=mapped_1_item_node,
        b=mapped_1_const_node,
        c=mapped_2_item_add_node,
        d=mapped_2_const_add_node,
    )
    concat_node = list_of_list_node.concat()
    sum_node = concat_node.sum()

    p = stitch.stitch([sum_node])

    def assert_node_calls(node, expected_call_names):
        found_calls = set([c.node.from_op.name for c in p.get_result(node).calls])
        expected_calls = set(expected_call_names)
        assert found_calls == expected_calls

    assert_node_calls(const_list_node, ["list-__getitem__"])
    assert_node_calls(indexed_node, ["list", "mapped_number-add"])
    assert_node_calls(fn_node, [])
    assert_node_calls(arr_1_node, ["list"])
    assert_node_calls(arr_2_node, ["mapped_number-add"])
    assert_node_calls(mapped_1_node, [])
    assert_node_calls(mapped_2_node, [])
    assert_node_calls(mapped_1_item_node, ["list"])
    assert_node_calls(mapped_1_const_node, ["list", "mapped_number-add"])
    assert_node_calls(mapped_2_item_node, ["mapped_number-add"])
    assert_node_calls(mapped_2_const_node, ["list", "mapped_number-add"])
    assert_node_calls(mapped_2_item_add_node, ["list"])
    assert_node_calls(mapped_2_const_add_node, ["list"])
    assert_node_calls(list_of_list_node, ["concat"])
    assert_node_calls(concat_node, ["numbers-sum"])
    assert_node_calls(sum_node, [])
