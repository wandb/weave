import weave

from .. import stitch

from ..language_features.tagging import make_tag_getter_op
from .. import compile_table
from weave import context_state as _context

_loading_builtins_token = _context.set_loading_built_ins()


@weave.type()
class TestPlanObject:
    _name: str
    val: int

    # Because this is named "Test*", doing .name() will tag the result
    @weave.op()
    def name(self) -> str:
        return self._name


@weave.type()
class TestPlanHasObject:
    name: str
    _obj: TestPlanObject


# Because this is named "Test*", doing .name() will tag the result
@weave.op()
def _test_hasobj_obj(self_has_obj: TestPlanHasObject) -> TestPlanObject:
    return self_has_obj._obj


get_object_self_tag = make_tag_getter_op.make_tag_getter_op("self", TestPlanObject.WeaveType())  # type: ignore
get_hasobject_self_tag = make_tag_getter_op.make_tag_getter_op("self_has_obj", TestPlanHasObject.WeaveType())  # type: ignore

_context.clear_loading_built_ins(_loading_builtins_token)


def test_traverse_tags():
    obj_node = weave.save(TestPlanObject("a", 1))
    obj_from_tag_val_node = get_object_self_tag(obj_node.name() + "hello").val
    p = stitch.stitch([obj_from_tag_val_node])
    obj_recorder = p.get_result(obj_node)
    assert len(obj_recorder.calls) == 2
    assert obj_recorder.calls[0].op_name == "TestPlanObject-name"
    assert obj_recorder.calls[1].op_name == "Object-__getattr__"
    assert obj_recorder.calls[1].inputs[1].val == "val"


def test_traverse_tags_2level():
    obj_node = weave.save(TestPlanHasObject("has", TestPlanObject("a", 1)))
    name_add_node = obj_node._test_hasobj_obj().name() + "hello"
    obj_from_tag_val_node = get_hasobject_self_tag(
        get_object_self_tag(name_add_node)
    ).name
    p = stitch.stitch([obj_from_tag_val_node])
    obj_recorder = p.get_result(obj_node)
    assert len(obj_recorder.calls) == 2
    assert obj_recorder.calls[0].op_name == "op-_test_hasobj_obj"
    assert obj_recorder.calls[1].op_name == "Object-__getattr__"
    assert obj_recorder.calls[1].inputs[1].val == "name"


def test_enter_filter():
    objs_node = weave.save([{"a": 5, "b": 6, "c": 10}, {"a": 7, "b": 8, "c": 11}])
    p = stitch.stitch([objs_node["b"], objs_node.filter(lambda obj: obj["a"] > 6)])
    obj_recorder = p.get_result(objs_node)
    calls = obj_recorder.calls
    assert len(calls) == 2
    assert calls[0].op_name == "mapped_typedDict-pick"
    assert calls[0].inputs[1].val == "b"
    assert calls[1].op_name == "typedDict-pick"
    assert calls[1].inputs[1].val == "a"


def test_travese_dict():
    obj_node = weave.save(TestPlanObject("a", 1))
    p = stitch.stitch([weave.ops.dict_(x=obj_node)["x"].name()])
    obj_recorder = p.get_result(obj_node)
    assert len(obj_recorder.calls) == 1
    assert obj_recorder.calls[0].op_name == "TestPlanObject-name"


def test_travese_groupby_dict():
    obj_node = weave.save([{"o": {"a": 5}, "x": 1}])
    grouped = obj_node.groupby(lambda row: weave.ops.dict_(x=row["o"]))
    output = grouped[0]["x"]
    groupkey_output = grouped[0].groupkey()["x"]["a"]
    p = stitch.stitch([output, groupkey_output])
    obj_recorder = p.get_result(obj_node)

    assert compile_table.get_projection(obj_recorder) == {"o": {"a": {}}, "x": {}}
