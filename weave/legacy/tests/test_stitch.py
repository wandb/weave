import typing

import pytest

import weave
from weave.legacy.weave import compile_domain, compile_table, weave_internal
from weave.legacy.weave import context_state as _context
from weave.legacy.weave.language_features.tagging import make_tag_getter_op
from weave.legacy.weave.ops_domain import run_ops

from ...legacy.weave import stitch
from ...tests import fixture_fakewandb as fwb
from . import test_wb

_loading_builtins_token = _context.set_loading_built_ins()


@weave.type()
class _TestPlanObject:
    _horse: str
    val: int

    # Because this is named "Test*", doing .horse() will tag the result
    @weave.op()
    def horse(self) -> str:
        return self._horse


@weave.type()
class _TestPlanHasObject:
    horse: str
    _obj: _TestPlanObject


@weave.op()
def dummy_no_arg_op() -> typing.List[_TestPlanObject]:
    return [_TestPlanObject("x", 1)]


# Because this is named "Test*", doing .name() will tag the result
@weave.op()
def _test_hasobj_obj(self_has_obj: _TestPlanHasObject) -> _TestPlanObject:
    return self_has_obj._obj


get_object_self_tag = make_tag_getter_op.make_tag_getter_op(
    "self", _TestPlanObject.WeaveType()
)  # type: ignore
get_hasobject_self_tag = make_tag_getter_op.make_tag_getter_op(
    "self_has_obj", _TestPlanHasObject.WeaveType()
)  # type: ignore

_context.clear_loading_built_ins(_loading_builtins_token)


def test_traverse_tags():
    obj_node = weave.save(_TestPlanObject("a", 1))
    obj_from_tag_val_node = get_object_self_tag(obj_node.horse() + "hello").val
    p = stitch.stitch([obj_from_tag_val_node])
    obj_recorder = p.get_result(obj_node)
    assert len(obj_recorder.calls) == 2
    assert obj_recorder.calls[0].node.from_op.name == "_TestPlanObject-horse"
    assert obj_recorder.calls[1].node.from_op.name == "Object-__getattr__"
    assert obj_recorder.calls[1].inputs[1].val == "val"


def test_traverse_tags_2level():
    obj_node = weave.save(_TestPlanHasObject("has", _TestPlanObject("a", 1)))
    name_add_node = obj_node._test_hasobj_obj().horse() + "hello"
    obj_from_tag_val_node = get_hasobject_self_tag(
        get_object_self_tag(name_add_node)
    ).horse
    p = stitch.stitch([obj_from_tag_val_node])
    obj_recorder = p.get_result(obj_node)
    assert len(obj_recorder.calls) == 2
    assert obj_recorder.calls[0].node.from_op.name == "op-_test_hasobj_obj"
    assert obj_recorder.calls[1].node.from_op.name == "Object-__getattr__"
    assert obj_recorder.calls[1].inputs[1].val == "horse"


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
    assert calls[1].node.from_op.name == "typedDict-pick"
    assert calls[1].inputs[1].val == "b"
    assert calls[2].node.from_op.name == "typedDict-pick"
    assert calls[2].inputs[1].val == "a"


def test_tag_access_in_filter_expr():
    objs_node = weave.save([_TestPlanObject("a", 1), _TestPlanObject("b", 2)])
    leaf = objs_node.horse().filter(lambda obj: get_object_self_tag(obj).val > 2)
    p = stitch.stitch([leaf])
    obj_recorder = p.get_result(objs_node)
    calls = obj_recorder.calls
    assert len(calls) == 2
    assert calls[0].node.from_op.name == "mapped__TestPlanObject-horse"
    assert calls[1].node.from_op.name == "Object-__getattr__"
    assert calls[1].inputs[1].val == "val"


def test_traverse_dict():
    obj_node = weave.save(_TestPlanObject("a", 1))
    p = stitch.stitch([weave.legacy.weave.ops.dict_(x=obj_node)["x"].horse()])
    obj_recorder = p.get_result(obj_node)
    assert len(obj_recorder.calls) == 1
    assert obj_recorder.calls[0].node.from_op.name == "_TestPlanObject-horse"


def test_travese_groupby_dict():
    obj_node = weave.save([{"o": {"a": 5}, "x": 1}])
    grouped = obj_node.groupby(lambda row: weave.legacy.weave.ops.dict_(x=row["o"]))
    output = grouped[0]["x"]
    groupkey_output = grouped[0].groupkey()["x"]["a"]
    p = stitch.stitch([output, groupkey_output])
    obj_recorder = p.get_result(obj_node)

    assert compile_table.get_projection(obj_recorder) == {"o": {"a": {}}, "x": {}}


def test_zero_arg_ops():
    node = dummy_no_arg_op()
    p = stitch.stitch([node])
    obj_recorder = p.get_result(node)
    assert obj_recorder.calls == []

    p = stitch.stitch([node.horse()])
    obj_recorder = p.get_result(node)
    assert len(obj_recorder.calls) == 1
    assert obj_recorder.calls[0].node.from_op.name == "mapped__TestPlanObject-horse"

    p = stitch.stitch([node.filter(lambda x: x._get_op("horse")() != "")])
    obj_recorder = p.get_result(node)
    assert len(obj_recorder.calls) == 1
    assert obj_recorder.calls[0].node.from_op.name == "_TestPlanObject-horse"

    p = stitch.stitch([node.filter(lambda x: x._get_op("horse")() != ""), node.horse()])
    obj_recorder = p.get_result(node)
    assert len(obj_recorder.calls) == 2
    assert obj_recorder.calls[0].node.from_op.name == "_TestPlanObject-horse"
    assert obj_recorder.calls[1].node.from_op.name == "mapped__TestPlanObject-horse"


def test_shared_fn_node():
    const_list_node = weave.legacy.weave.ops.make_list(a=1, b=2)
    indexed_node = const_list_node[0]
    arr_1_node = weave.legacy.weave.ops.make_list(a=1, b=2, c=3)
    arr_2_node = weave.legacy.weave.ops.make_list(a=10, b=20, c=30)

    mapped_1_node = arr_1_node.map(
        lambda row: weave.legacy.weave.ops.dict_(item=row, const=indexed_node)
    )
    mapped_2_node = arr_2_node.map(
        lambda row: weave.legacy.weave.ops.dict_(item=row, const=indexed_node)
    )

    mapped_1_item_node = mapped_1_node["item"]
    mapped_1_const_node = mapped_1_node["const"]
    mapped_2_item_node = mapped_2_node["item"]
    mapped_2_const_node = mapped_2_node["const"]

    mapped_2_item_add_node = mapped_2_item_node + 100
    mapped_2_const_add_node = mapped_2_const_node + 100

    list_of_list_node = weave.legacy.weave.ops.make_list(
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

    assert_node_calls(const_list_node, ["list", "mapped_number-add"])
    assert_node_calls(indexed_node, ["list", "mapped_number-add"])
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


def test_stitch_keytypes_override_fetch_all_columns(fake_wandb):
    fake_wandb.fake_api.add_mock(test_wb.table_mock_filtered)
    keytypes_node = weave.legacy.weave.ops.object_keytypes(
        run_ops.run_tag_getter_op(
            weave.legacy.weave.ops.project("stacey", "mendeleev")
            .filteredRuns("{}", "-createdAt")
            .limit(50)
            .summary()
            .pick("table")
            .table()
            .rows()
        ).summary()
    )

    p = stitch.stitch([keytypes_node])
    object_recorder = p.get_result(keytypes_node)
    key_tree = compile_table.get_projection(object_recorder)

    # even though we have picked a specific key out of the table, we should still have an empty key tree
    # because we must fetch all columns due to keytypes
    assert key_tree == {}


def test_stitch_overlapping_tags(fake_wandb):
    fake_wandb.fake_api.add_mock(
        lambda a, b: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,
                "runs_261949318143369aa6c158af92afee03": {
                    "edges": [{"node": {**fwb.run_payload, "summaryMetrics": "{}"}}]
                },
                "runs_30ea80144a38a5c57c80d9d7f0485166": {
                    "edges": [
                        {"node": {**fwb.run_payload, "summaryMetrics": '{"a": 1}'}}
                    ]
                },
            }
        }
    )
    project_node = weave.legacy.weave.ops.project("stacey", "mendeleev")
    filtered_runs_a_node = project_node.filteredRuns("{}", "-createdAt")[0]
    summary_a_node = filtered_runs_a_node.summary()
    tagged_name_a = weave.legacy.weave.ops.run_ops.run_tag_getter_op(
        summary_a_node["a"]
    ).name()
    filtered_runs_b_node = project_node.filteredRuns("{}", "+createdAt")[0]
    summary_b_node = filtered_runs_b_node.summary()
    tagged_id_b = weave.legacy.weave.ops.run_ops.run_tag_getter_op(summary_b_node).id()

    p = stitch.stitch([tagged_name_a, tagged_id_b])

    assert len(p.get_result(project_node).tags) == 0
    assert len(p.get_result(filtered_runs_a_node).calls) == 2
    assert len(p.get_result(filtered_runs_b_node).calls) == 2


def test_refine_history_type_included_in_gql():
    project_node = weave.legacy.weave.ops.project("stacey", "mendeleev")
    runs_node = project_node.runs()
    map_node = runs_node.map(lambda row: weave.legacy.weave.ops.dict_(variant=row))
    checkpoint_node = map_node.createIndexCheckpointTag()
    index_node = checkpoint_node[0]
    pick_node = index_node["variant"]
    refine_history_node = pick_node.refine_history_type()
    sg = stitch.stitch([refine_history_node])
    assert "historyKeys" in compile_domain._get_fragment(project_node, sg)


def test_stitch_missing_key():
    a_node = weave_internal.make_const_node(weave.types.String(), "a")
    dict_node = weave.legacy.weave.ops.dict_(a=a_node)
    picked_valid = dict_node["a"] + "-suffix"
    picked_missing = dict_node["b"] + "-suffix"

    assert weave.use(picked_valid) == "a-suffix"
    assert weave.use(picked_missing) == None

    sg = stitch.stitch([picked_valid, picked_missing])

    assert len(sg.get_result(a_node).calls) == 1
