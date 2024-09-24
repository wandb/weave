import pytest

import weave
from weave.legacy.weave import box, weave_internal
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.artifact_fs import FilesystemArtifactFileType
from weave.legacy.weave.language_features.tagging import (
    make_tag_getter_op,
    tag_store,
    tagged_value_type,
    tagged_value_type_helpers,
)
from weave.legacy.weave.ops_domain.run_ops import run_tag_getter_op
from weave.legacy.weave.ops_domain.wb_domain_types import ProjectType, Run, RunType
from weave.legacy.weave.ops_primitives import dict as dict_ops
from weave.legacy.weave.ops_primitives import list_ as list_ops


def test_tagged_value():
    tv = tagged_value_type.TaggedValueType(
        types.TypedDict({"a": types.Number()}), types.String()
    )
    assert tv.value == types.String()
    assert tv.tag == types.TypedDict({"a": types.Number()})


def test_tagged_types():
    @weave.type()
    class _TestNumber:
        inner: int

    from weave.legacy.weave import context_state

    _loading_builtins_token = context_state.set_loading_built_ins()

    @weave.op()
    def add_tester(a: _TestNumber, b: _TestNumber) -> _TestNumber:
        return _TestNumber(a.inner + b.inner)

    @weave.op()
    def add_tester_2(d: _TestNumber, e: _TestNumber) -> _TestNumber:
        return _TestNumber(d.inner + e.inner)

    get_a_tag = make_tag_getter_op.make_tag_getter_op("a", _TestNumber.WeaveType())
    get_d_tag = make_tag_getter_op.make_tag_getter_op("d", _TestNumber.WeaveType())

    context_state.clear_loading_built_ins(_loading_builtins_token)

    # 1: Assert that that the tester works
    three = add_tester(_TestNumber(1), _TestNumber(2))
    assert weave.use(three).inner == 3

    # 2: Assert that we can get a tag
    assert weave.use(get_a_tag(three)).inner == 1

    # 3: Assert that we can use tagged values instead of raw values
    seven = add_tester(_TestNumber(3), _TestNumber(4))
    ten = add_tester_2(three, seven)
    assert tt(
        {"a": _TestNumber.WeaveType(), "d": _TestNumber.WeaveType()},
        _TestNumber.WeaveType(),
    ).assign_type(ten.type)
    assert (
        isinstance(ten.type, tagged_value_type.TaggedValueType)
        and isinstance(
            ten.type.tag.property_types["d"], tagged_value_type.TaggedValueType
        )
        and isinstance(ten.type.tag.property_types["d"].value, _TestNumber.WeaveType)
    )
    assert weave.use(ten).inner == 10

    # 4: Show that tags flow through
    assert weave.use(get_a_tag(ten)).inner == 1
    assert weave.use(get_d_tag(ten)).inner == 3

    # 5: Show that saving works:
    ten = weave.save(ten)
    assert weave.use(ten).inner == 10
    assert weave.use(get_a_tag(ten)).inner == 1


def test_index_checkpoint():
    arr = weave.save([1, 2, 3, 4])
    assert weave.use(arr) == [1, 2, 3, 4]
    tagged_arr = arr.createIndexCheckpointTag()
    assert weave.use(tagged_arr) == [1, 2, 3, 4]
    first_item = tagged_arr[0]
    assert weave.use(first_item) == 1
    first_item_index = first_item.indexCheckpoint()
    assert weave.use(first_item_index) == 0
    assert weave.use(tagged_arr[3].indexCheckpoint()) == 3


def tt(tag_dict, value_type):
    return tagged_value_type.TaggedValueType(types.TypedDict(tag_dict), value_type)


### Test Suite v2
@pytest.mark.parametrize(
    "target_type, next_type, is_assignable",
    [
        # empty tags and no tags
        (tt({}, types.Any()), types.Number(), False),
        (tt({}, types.Number()), types.Number(), False),
        (tt({}, types.String()), types.Number(), False),
        # no tags and empty tags
        (types.Any(), tt({}, types.Number()), True),
        (types.Number(), tt({}, types.Number()), True),
        (types.String(), tt({}, types.Number()), False),
        # no tags and some tags
        (types.Any(), tt({"a": types.Number()}, types.Number()), True),
        (types.Number(), tt({"a": types.Number()}, types.Number()), True),
        (types.String(), tt({"a": types.Number()}, types.Number()), False),
        # empty tags and empty tags
        (tt({}, types.Any()), tt({}, types.Number()), True),
        (tt({}, types.Number()), tt({}, types.Number()), True),
        (tt({}, types.String()), tt({}, types.Number()), False),
        # missing Tags
        (tt({"a": types.Number()}, types.Any()), tt({}, types.Number()), False),
        (tt({"a": types.Number()}, types.Number()), tt({}, types.Number()), False),
        (tt({"a": types.Number()}, types.String()), tt({}, types.Number()), False),
        # tag match
        (
            tt({"a": types.Number()}, types.Any()),
            tt({"a": types.Number()}, types.Number()),
            True,
        ),
        (
            tt({"a": types.Number()}, types.Number()),
            tt({"a": types.Number()}, types.Number()),
            True,
        ),
        (
            tt({"a": types.Number()}, types.String()),
            tt({"a": types.Number()}, types.Number()),
            False,
        ),
        # tag mismatch
        (
            tt({"a": types.Number()}, types.Any()),
            tt({"b": types.Number()}, types.Number()),
            False,
        ),
        (
            tt({"a": types.Number()}, types.Number()),
            tt({"b": types.Number()}, types.Number()),
            False,
        ),
        (
            tt({"a": types.Number()}, types.String()),
            tt({"b": types.Number()}, types.Number()),
            False,
        ),
        # tag superset
        (
            tt({"a": types.Number()}, types.Any()),
            tt({"a": types.Number(), "b": types.String()}, types.Number()),
            True,
        ),
        (
            tt({"a": types.Number()}, types.Number()),
            tt({"a": types.Number(), "b": types.String()}, types.Number()),
            True,
        ),
        (
            tt({"a": types.Number()}, types.String()),
            tt({"a": types.Number(), "b": types.String()}, types.Number()),
            False,
        ),
    ],
)
def test_tagged_value_assignment(target_type, next_type, is_assignable):
    assert target_type.assign_type(next_type) == is_assignable


def test_tag_lookups():
    @weave.type()
    class TestObj:
        inner: int

    # Test Simple Lookup
    obj_1 = TestObj(1)
    tag_store.add_tags(obj_1, {"a": 1})
    assert tag_store.find_tag(obj_1, "a") == 1

    obj_2 = TestObj(1)
    tag_store.add_tags(obj_2, {"a": 2, "b": 2})
    assert tag_store.find_tag(obj_2, "a") == 2
    assert tag_store.find_tag(obj_2, "b") == 2

    # Test Ancestor Lookup with name overlap
    obj_3 = TestObj(1)
    tag_store.add_tags(obj_3, {"nest": obj_2, "b": 3})
    assert tag_store.find_tag(obj_3, "a") == 2
    assert tag_store.find_tag(tag_store.find_tag(obj_3, "nest"), "b") == 2
    assert tag_store.find_tag(obj_3, "b") == 3


def test_tag_scope_with_multiple_children():
    list_node = weave.save([1, 2, 3])
    indexed = list_node.createIndexCheckpointTag()
    count_node = indexed.count()
    first_node = indexed[0]
    second_node = indexed[1]
    first_tag = first_node.indexCheckpoint()
    second_tag = second_node.indexCheckpoint()
    assert weave.use(count_node) == 3
    assert weave.use([first_tag, second_tag]) == [0, 1]


def test_nested_deserialization_of_weave0_tags():
    weave_0_tag_dict = {
        "type": "tagged",
        "tag": {
            "type": "union",
            "members": [
                {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {"a": "string"},
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {"b": "number"},
                    },
                },
                {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {"c": "boolean"},
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {"d": "project"},
                    },
                },
            ],
        },
        "value": {
            "type": "typedDict",
            "propertyTypes": {"e": "run"},
        },
    }
    weave_1_type = tagged_value_type.TaggedValueType.from_dict(weave_0_tag_dict)
    assert weave_1_type == tagged_value_type.TaggedValueType(
        types.TypedDict(
            {
                "a": types.optional(types.String()),
                "b": types.optional(types.Number()),
                "c": types.optional(types.Boolean()),
                "d": types.optional(ProjectType),
            }
        ),
        types.TypedDict(
            {
                "e": RunType,
            }
        ),
    )


def test_keytypes_tagged():
    object = box.box({"b": 1, "c": "a"})
    tag_store.add_tags(object, {"run": Run()})
    object_node = weave.save(object)

    kt_node = dict_ops.object_keytypes(object_node)
    assert weave.use(kt_node) == [
        {"key": "b", "type": types.Int()},
        {"key": "c", "type": types.String()},
    ]
    assert kt_node.type == tagged_value_type.TaggedValueType(
        types.TypedDict({"run": RunType.with_keys({})}),
        types.List(
            object_type=types.TypedDict(
                property_types={
                    "key": types.String(),
                    "type": types.TypeType(attr_types={}),
                }
            )
        ),
    )


@pytest.mark.parametrize(
    "list_data",
    [
        lambda: box.box([1, 2, 3]),
        lambda: box.box(
            [
                tag_store.add_tags(box.box(elem), {"int": i})
                for i, elem in enumerate([1, 2, 3])
            ]
        ),
    ],
)
def test_list_tags_accessible_to_map_elements(list_data):
    run = Run()
    tag_type = types.TypedDict({"run": RunType.with_keys({})})
    tagged = tag_store.add_tags(list_data(), {"run": run})
    saved_node = weave.save(tagged)
    map_fn = lambda row: run_tag_getter_op(row)
    fn = weave_internal.define_fn(
        {"row": tagged_value_type.TaggedValueType(tag_type, types.Int())}, map_fn
    )
    mapped = list_ops.List.map(saved_node, fn)
    assert weave.use(mapped) == [run, run, run]


def test_unwrap_rewrap_tags():
    t1 = tagged_value_type.TaggedValueType(
        types.TypedDict({"a": types.Int()}), types.Int()
    )

    unwrapped, rewrap = tagged_value_type_helpers.unwrap_tags(t1)
    assert unwrapped == types.Int()
    assert rewrap(unwrapped) == t1

    t2 = tagged_value_type.TaggedValueType(
        types.TypedDict({"a": types.Int()}), types.TypedDict({"b": types.Int()})
    )

    unwrapped, rewrap = tagged_value_type_helpers.unwrap_tags(t2)
    assert unwrapped == types.TypedDict({"b": types.Int()})
    assert rewrap(unwrapped) == t2

    t3 = tagged_value_type.TaggedValueType(
        types.TypedDict({"a": types.Int()}),
        tagged_value_type.TaggedValueType(
            types.TypedDict({"c": types.TypeType()}),
            types.TypedDict({"b": types.Int()}),
        ),
    )

    unwrapped, rewrap = tagged_value_type_helpers.unwrap_tags(t3)
    assert unwrapped == types.TypedDict({"b": types.Int()})
    assert rewrap(unwrapped) == t3

    t4 = types.TypedDict({"d": types.Int()})
    assert rewrap(t4) == tagged_value_type.TaggedValueType(
        types.TypedDict({"a": types.Int()}),
        tagged_value_type.TaggedValueType(
            types.TypedDict({"c": types.TypeType()}),
            types.TypedDict({"d": types.Int()}),
        ),
    )

    t5 = tagged_value_type.TaggedValueType(
        types.TypedDict({"a": types.Int()}),
        tagged_value_type.TaggedValueType(
            types.TypedDict({"c": types.TypeType()}),
            types.TypedDict({"d": types.List(types.String())}),
        ),
    )

    unwrapped, rewrap = tagged_value_type_helpers.unwrap_tags(t5)
    assert unwrapped == types.TypedDict({"d": types.List(types.String())})
    assert rewrap(unwrapped) == t5

    t6 = types.Int()
    unwrapped, rewrap = tagged_value_type_helpers.unwrap_tags(t6)
    assert unwrapped == t6
    assert rewrap(unwrapped) == t6
