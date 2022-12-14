import dataclasses
import pytest
from ..language_features.tagging.tagged_value_type import TaggedValueType
import weave
import weave.weave_types
from .. import weave_types as types
from .. import runs
from ..ops_primitives import _dict_utils
from rich import print


def test_typeof_string():
    t = types.TypeRegistry.type_of("x")
    assert t == types.String()


def test_typeof_list_const_string():
    t = types.TypeRegistry.type_of(["x"])
    assert t == types.List(types.String())


def test_serialize_const_string():
    t = types.Const(types.String(), "x")
    ser = t.to_dict()
    deser = types.TypeRegistry.type_from_dict(ser)
    assert t == deser


def test_merge_typedict_keys_are_stable():
    for i in range(10):
        t = types.TypedDict(
            {"a": types.String(), "b": types.String(), "c": types.String()}
        )
        t2 = types.TypedDict(
            {"a": types.String(), "b": types.String(), "c": types.String()}
        )
        r = types.merge_types(t, t2)
        assert list(r.property_types.keys()) == ["a", "b", "c"]


def test_merge_through_tags():
    t = TaggedValueType(
        types.TypedDict({"tag": types.Number()}),
        types.TypedDict(
            {"a": types.String(), "b": types.Number(), "c": types.String()}
        ),
    )
    t2 = TaggedValueType(
        types.TypedDict({"tag": types.Number()}),
        types.TypedDict(
            {"a": types.String(), "b": types.String(), "d": types.String()}
        ),
    )
    r = types.merge_types(t, t2)
    correct_type = types.UnionType(t, t2)
    assert correct_type.assign_type(r)
    assert r.assign_type(correct_type)


def test_typeof_bool():
    assert types.TypeRegistry.type_of(False) == types.Boolean()


def test_typeof_type():
    assert types.TypeRegistry.type_of(types.Int()) == types.TypeType()


def test_type_tofromdict():
    d = types.TypeType().to_dict()
    assert types.TypeRegistry.type_from_dict(d) == types.TypeType()


def test_typeof_list_runs():
    l = [
        runs.Run("a", "op", inputs={"a": "x"}, output=4.9),
        runs.Run("b", "op", inputs={"a": "x", "b": 9}, output=3.3),
    ]
    actual = types.TypeRegistry.type_of(l)
    print("test_typeof_list_runs.actual", actual)

    assert actual == types.List(
        types.UnionType(
            types.RunType(
                inputs=types.TypedDict({"a": types.String()}),
                history=types.List(types.UnknownType()),
                output=types.Float(),
            ),
            types.RunType(
                inputs=types.TypedDict({"a": types.String(), "b": types.Int()}),
                history=types.List(types.UnknownType()),
                output=types.Float(),
            ),
        )
    )


def test_typeof_list_dict_merge():
    d = [{"a": 6, "b": "x"}, {"a": 5, "b": None}]
    assert types.TypeRegistry.type_of(d) == types.List(
        types.TypedDict({"a": types.Int(), "b": types.optional(types.String())})
    )


def test_typeof_nested_dict_merge():
    """Tests that nested merging is disabled."""
    t1 = weave.weave_types.TypedDict(
        {"a": weave.weave_types.TypedDict({"b": types.Int()})}
    )
    t2 = weave.weave_types.TypedDict(
        {"a": weave.weave_types.TypedDict({"c": types.String()})}
    )
    merged_type = _dict_utils.typeddict_merge_output_type({"self": t1, "other": t2})
    assert merged_type == weave.weave_types.TypedDict(
        {"a": weave.weave_types.TypedDict({"c": types.String()})}
    )


def test_dict_without_key_type():
    fully_typed = weave.weave_types.TypeRegistry.type_from_dict(
        {"type": "dict", "keyType": "string", "objectType": "number"}
    )
    partial_typed = weave.weave_types.TypeRegistry.type_from_dict(
        {"type": "dict", "objectType": "number"}
    )
    assert fully_typed.assign_type(partial_typed)


def test_union_access():
    ### Type return

    # Not all members have props
    unioned = weave.weave_types.union(
        weave.weave_types.String(), weave.weave_types.List(weave.weave_types.String())
    )
    with pytest.raises(AttributeError):
        unioned.object_type

    # Combined dicts
    unioned = weave.weave_types.union(
        weave.weave_types.List(weave.weave_types.String()),
        weave.weave_types.List(weave.weave_types.Number()),
    )
    assert unioned.object_type == weave.weave_types.union(
        weave.weave_types.String(), weave.weave_types.Number()
    )

    # Nullable type
    unioned = weave.weave_types.union(
        weave.weave_types.NoneType(), weave.weave_types.List(weave.weave_types.String())
    )
    assert unioned.object_type == weave.weave_types.union(
        weave.weave_types.String(), weave.weave_types.NoneType()
    )

    ### Dict Return
    # Not all members have props
    unioned = weave.weave_types.union(
        weave.weave_types.String(),
        weave.weave_types.TypedDict({"a": weave.weave_types.String()}),
    )
    with pytest.raises(AttributeError):
        unioned.property_types

    # Combined dicts
    unioned = weave.weave_types.union(
        weave.weave_types.TypedDict(
            {
                "same": weave.weave_types.Number(),
                "solo_a": weave.weave_types.Number(),
                "differ": weave.weave_types.Number(),
            }
        ),
        weave.weave_types.TypedDict(
            {
                "same": weave.weave_types.Number(),
                "solo_b": weave.weave_types.String(),
                "differ": weave.weave_types.String(),
            }
        ),
    )
    assert unioned.property_types == {
        "same": weave.weave_types.Number(),
        "solo_a": weave.weave_types.union(
            weave.weave_types.Number(), weave.weave_types.NoneType()
        ),
        "solo_b": weave.weave_types.union(
            weave.weave_types.String(), weave.weave_types.NoneType()
        ),
        "differ": weave.weave_types.union(
            weave.weave_types.Number(), weave.weave_types.String()
        ),
    }

    # Nullable type
    unioned = weave.weave_types.union(
        weave.weave_types.NoneType(),
        weave.weave_types.TypedDict({"a": weave.weave_types.String()}),
    )
    assert unioned.property_types == {
        "a": weave.weave_types.union(
            weave.weave_types.String(), weave.weave_types.NoneType()
        )
    }


def test_typeof_node():
    n = weave.save(5)
    assert weave.type_of(n + 5) == types.Function({}, types.Number())


@dataclasses.dataclass(frozen=True)
class SublistType(types.Type):
    _base_type = types.List(types.Any())
    object_type: types.Type = types.UnknownType()


def test_subtype_list():
    assert types.List(types.Int()).assign_type(types.List(types.Int()))
    assert not types.List(types.String()).assign_type(types.List(types.Int()))

    assert types.List(types.Int()).assign_type(SublistType(types.Int()))
    assert not types.List(types.String()).assign_type(SublistType(types.Int()))


def test_typeddict_to_dict():
    assert types.Dict(types.String(), types.Int()).assign_type(
        types.TypedDict({"a": types.Int(), "b": types.Int()})
    )
    assert not types.Dict(types.String(), types.Int()).assign_type(
        types.TypedDict({"a": types.Int(), "b": types.String()})
    )


# The following test tests all permutionations of container types Consts, Tags,
# and Unions. Note: we might deicde to disallow consts of unions which would
# make some of these tests not applicable. However, this is exhastive given our
# current implementation.
@pytest.mark.parametrize(
    "in_type, out_type",
    [
        # Units
        (types.Number(), types.Number()),
        (types.NoneType(), types.Invalid()),
        # Const Units
        (
            types.Const(types.Number(), 5),
            types.Const(types.Number(), 5),
        ),
        (types.Const(types.NoneType(), None), types.Invalid()),
        # Tagged Units
        (
            TaggedValueType(types.TypedDict({}), types.Number()),
            TaggedValueType(types.TypedDict({}), types.Number()),
        ),
        (
            TaggedValueType(types.TypedDict({}), types.NoneType()),
            TaggedValueType(types.TypedDict({}), types.Invalid()),
        ),
        # Tagged Const Units
        (
            TaggedValueType(types.TypedDict({}), types.Const(types.Number(), 5)),
            TaggedValueType(types.TypedDict({}), types.Const(types.Number(), 5)),
        ),
        (
            TaggedValueType(types.TypedDict({}), types.Const(types.NoneType(), None)),
            TaggedValueType(types.TypedDict({}), types.Invalid()),
        ),
        # Const Tagged Units
        (
            types.Const(TaggedValueType(types.TypedDict({}), types.Number()), 5),
            types.Const(TaggedValueType(types.TypedDict({}), types.Number()), 5),
        ),
        (
            types.Const(TaggedValueType(types.TypedDict({}), types.NoneType()), None),
            TaggedValueType(types.TypedDict({}), types.Invalid()),
        ),
        # Union Units
        (types.union(types.NoneType(), types.Number()), types.Number()),
        (
            types.union(types.String(), types.Number()),
            types.union(types.String(), types.Number()),
        ),
        # Union Const Units
        (
            types.union(
                types.Const(types.NoneType(), None), types.Const(types.Number(), 5)
            ),
            types.Const(types.Number(), 5),
        ),
        (
            types.union(
                types.Const(types.String(), "hello"), types.Const(types.Number(), 5)
            ),
            types.union(
                types.Const(types.String(), "hello"), types.Const(types.Number(), 5)
            ),
        ),
        # Union Tagged Units
        (
            types.union(
                TaggedValueType(types.TypedDict({}), types.NoneType()),
                TaggedValueType(types.TypedDict({}), types.Number()),
            ),
            TaggedValueType(types.TypedDict({}), types.Number()),
        ),
        (
            types.union(
                TaggedValueType(types.TypedDict({}), types.String()),
                TaggedValueType(types.TypedDict({}), types.Number()),
            ),
            types.union(
                TaggedValueType(types.TypedDict({}), types.String()),
                TaggedValueType(types.TypedDict({}), types.Number()),
            ),
        ),
        # Union Tagged Consts Units
        (
            types.union(
                TaggedValueType(types.TypedDict({}), types.NoneType()),
                TaggedValueType(types.TypedDict({}), types.Const(types.Number(), 5)),
            ),
            TaggedValueType(types.TypedDict({}), types.Const(types.Number(), 5)),
        ),
        (
            types.union(
                TaggedValueType(
                    types.TypedDict({}), types.Const(types.String(), "hello")
                ),
                TaggedValueType(types.TypedDict({}), types.Const(types.Number(), 5)),
            ),
            types.union(
                TaggedValueType(
                    types.TypedDict({}), types.Const(types.String(), "hello")
                ),
                TaggedValueType(types.TypedDict({}), types.Const(types.Number(), 5)),
            ),
        ),
        # Const Union Units
        (
            types.Const(types.union(types.NoneType(), types.Number()), 5),
            types.Number(),
        ),
        (  # this is a wierd case - maybe we should just disallow const unions?
            types.Const(types.union(types.NoneType(), types.Number()), None),
            types.Number(),
        ),
        # Const Union Tagged Units
        (
            types.Const(
                types.union(
                    TaggedValueType(types.TypedDict({}), types.NoneType()),
                    TaggedValueType(types.TypedDict({}), types.Number()),
                ),
                5,
            ),
            TaggedValueType(types.TypedDict({}), types.Number()),
        ),
        (
            types.Const(
                types.union(
                    TaggedValueType(types.TypedDict({}), types.String()),
                    TaggedValueType(types.TypedDict({}), types.Number()),
                ),
                5,
            ),
            types.Const(
                types.union(
                    TaggedValueType(types.TypedDict({}), types.String()),
                    TaggedValueType(types.TypedDict({}), types.Number()),
                ),
                5,
            ),
        ),
        # Tagged Union Units
        (
            TaggedValueType(
                types.TypedDict({}), types.union(types.NoneType(), types.Number())
            ),
            TaggedValueType(types.TypedDict({}), types.Number()),
        ),
        (
            TaggedValueType(
                types.TypedDict({}), types.union(types.String(), types.Number())
            ),
            TaggedValueType(
                types.TypedDict({}), types.union(types.String(), types.Number())
            ),
        ),
        # Tagged Union Const Units
        (
            TaggedValueType(
                types.TypedDict({}),
                types.union(
                    types.Const(types.NoneType(), None), types.Const(types.Number(), 5)
                ),
            ),
            TaggedValueType(types.TypedDict({}), types.Const(types.Number(), 5)),
        ),
        (
            TaggedValueType(
                types.TypedDict({}),
                types.union(
                    types.Const(types.String(), "hello"), types.Const(types.Number(), 5)
                ),
            ),
            TaggedValueType(
                types.TypedDict({}),
                types.union(
                    types.Const(types.String(), "hello"), types.Const(types.Number(), 5)
                ),
            ),
        ),
        # Union with multiple non-none members
        (
            types.union(types.NoneType(), types.Number(), types.String()),
            types.union(types.Number(), types.String()),
        ),
    ],
)
def test_non_none(in_type, out_type):
    assert types.non_none(in_type) == out_type


def test_floatint_merged():
    assert weave.type_of([1.0, 2.0]).object_type == types.Float()
    assert weave.type_of([1.0, 2]).object_type == types.Float()
    assert weave.type_of([1, 2]).object_type == types.Int()


def test_typetype():
    tt = weave.type_of(weave.types.TypedDict({"a": weave.types.Int()}))
    assert tt == weave.types.TypeType(
        attr_types={
            "property_types": weave.types.Dict(types.String(), types.TypeType())
        }
    )


def test_typetype_disjoint_from_normal_type_hierarchy():
    assert not weave.type_of(weave.types.List()).assign_type(weave.type_of(None))


def test_typetype_nodes():
    t = weave.save(weave.types.TypedDict({"a": weave.types.Int()}))
    assert weave.use(t.property_types) == {"a": weave.types.Int()}


def test_typetype_tofrom_dict():
    t = weave.type_of(types.TypedDict())
    d = t.to_dict()
    t2 = types.TypeType.from_dict(d)
    assert t == t2
