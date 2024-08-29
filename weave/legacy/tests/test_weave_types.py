import dataclasses

import pytest

import weave
import weave.legacy.weave
import weave.legacy.weave.weave_types
from weave.legacy.weave import _dict_utils, runs
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.language_features.tagging.tagged_value_type import TaggedValueType
from weave.legacy.weave.ops_domain import wbmedia

from ... import errors


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
    correct_type = TaggedValueType(
        types.TypedDict(property_types={"tag": types.Number()}),
        types.TypedDict(
            property_types={
                "a": types.String(),
                "b": types.UnionType(types.Number(), types.String()),
                "c": types.UnionType(types.String(), types.NoneType()),
                "d": types.UnionType(types.NoneType(), types.String()),
            }
        ),
    )
    assert correct_type.assign_type(r)
    assert r.assign_type(correct_type)


def test_merge_tag_union_unknown():
    t = TaggedValueType(
        types.TypedDict(property_types={"run": types.Int()}),
        types.TypedDict(
            property_types={
                "step": types.UnionType(types.NoneType(), types.Float()),
                "prompt": types.UnionType(types.NoneType(), types.String()),
                "image": types.UnionType(types.String(), types.NoneType()),
            }
        ),
    )
    t2 = TaggedValueType(
        types.TypedDict(property_types={"run": types.Int()}),
        types.TypedDict(
            property_types={
                "step": types.UnknownType(),
                "prompt": types.UnknownType(),
                "image": types.UnknownType(),
            }
        ),
    )
    r = types.merge_types(t, t2)
    assert r == t


def test_tagged_unions_simple():
    assert weave.types.optional(weave.types.Int()).assign_type(
        TaggedValueType(
            types.TypedDict({"a": weave.types.String()}),
            weave.types.optional(weave.types.Int()),
        )
    )


def test_tag_assignment_through_union():
    base = TaggedValueType(types.TypedDict({"a": types.Number()}), types.Any())
    t = TaggedValueType(types.TypedDict({"a": types.Number()}), types.String())
    t2 = TaggedValueType(types.TypedDict({"a": types.Number()}), types.Number())
    union = types.union(t, t2)
    t3 = TaggedValueType(types.TypedDict({"b": types.Number()}), union)
    assert base.assign_type(t3)


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
        types.RunType(
            inputs=types.TypedDict(
                {"a": types.String(), "b": types.optional(types.Int())}
            ),
            history=types.List(types.UnknownType()),
            output=types.Float(),
        ),
    )


def test_typeof_list_dict_merge():
    d = [{"a": 6, "b": "x"}, {"a": 5, "b": None}]
    assert types.TypeRegistry.type_of(d) == types.List(
        types.TypedDict({"a": types.Int(), "b": types.optional(types.String())})
    )


def test_typeof_nested_dict_merge():
    """Tests that nested merging is disabled."""
    t1 = weave.legacy.weave.weave_types.TypedDict(
        {"a": weave.legacy.weave.weave_types.TypedDict({"b": types.Int()})}
    )
    t2 = weave.legacy.weave.weave_types.TypedDict(
        {"a": weave.legacy.weave.weave_types.TypedDict({"c": types.String()})}
    )
    merged_type = _dict_utils.typeddict_merge_output_type({"self": t1, "other": t2})
    assert merged_type == weave.legacy.weave.weave_types.TypedDict(
        {"a": weave.legacy.weave.weave_types.TypedDict({"c": types.String()})}
    )


def test_dict_without_key_type():
    fully_typed = weave.legacy.weave.weave_types.TypeRegistry.type_from_dict(
        {"type": "dict", "keyType": "string", "objectType": "number"}
    )
    partial_typed = weave.legacy.weave.weave_types.TypeRegistry.type_from_dict(
        {"type": "dict", "objectType": "number"}
    )
    assert fully_typed.assign_type(partial_typed)


# def test_union_unknown():
#     assert (
#         weave.legacy.weave.weave_types.union(
#             weave.legacy.weave.weave_types.String(), weave.legacy.weave.weave_types.UnknownType()
#         )
#         == weave.legacy.weave.weave_types.String()
#     )
#     assert (
#         weave.legacy.weave.weave_types.union(
#             weave.legacy.weave.weave_types.UnknownType(), weave.legacy.weave.weave_types.UnknownType()
#         )
#         == weave.legacy.weave.weave_types.UnknownType()
#     )
#     assert (
#         weave.legacy.weave.weave_types.union(
#             weave.legacy.weave.weave_types.UnknownType(),
#             weave.legacy.weave.weave_types.UnknownType(),
#             weave.types.String(),
#         )
#         == weave.legacy.weave.weave_types.String()
#     )


def test_union_access():
    ### Type return

    # Not all members have props
    unioned = weave.legacy.weave.weave_types.union(
        weave.legacy.weave.weave_types.String(),
        weave.legacy.weave.weave_types.List(weave.legacy.weave.weave_types.String()),
    )
    with pytest.raises(AttributeError):
        unioned.object_type

    # Combined dicts
    unioned = weave.legacy.weave.weave_types.union(
        weave.legacy.weave.weave_types.List(weave.legacy.weave.weave_types.String()),
        weave.legacy.weave.weave_types.List(weave.legacy.weave.weave_types.Number()),
    )
    assert unioned.object_type == weave.legacy.weave.weave_types.union(
        weave.legacy.weave.weave_types.String(), weave.legacy.weave.weave_types.Number()
    )

    # Nullable type
    unioned = weave.legacy.weave.weave_types.union(
        weave.legacy.weave.weave_types.NoneType(),
        weave.legacy.weave.weave_types.List(weave.legacy.weave.weave_types.String()),
    )
    assert unioned.object_type == weave.legacy.weave.weave_types.union(
        weave.legacy.weave.weave_types.String(), weave.legacy.weave.weave_types.NoneType()
    )

    ### Dict Return
    # Not all members have props
    unioned = weave.legacy.weave.weave_types.union(
        weave.legacy.weave.weave_types.String(),
        weave.legacy.weave.weave_types.TypedDict({"a": weave.legacy.weave.weave_types.String()}),
    )
    with pytest.raises(AttributeError):
        unioned.property_types

    # Combined dicts
    unioned = weave.legacy.weave.weave_types.union(
        weave.legacy.weave.weave_types.TypedDict(
            {
                "same": weave.legacy.weave.weave_types.Number(),
                "solo_a": weave.legacy.weave.weave_types.Number(),
                "differ": weave.legacy.weave.weave_types.Number(),
            }
        ),
        weave.legacy.weave.weave_types.TypedDict(
            {
                "same": weave.legacy.weave.weave_types.Number(),
                "solo_b": weave.legacy.weave.weave_types.String(),
                "differ": weave.legacy.weave.weave_types.String(),
            }
        ),
    )
    assert unioned.property_types == {
        "same": weave.legacy.weave.weave_types.Number(),
        "solo_a": weave.legacy.weave.weave_types.union(
            weave.legacy.weave.weave_types.Number(), weave.legacy.weave.weave_types.NoneType()
        ),
        "solo_b": weave.legacy.weave.weave_types.union(
            weave.legacy.weave.weave_types.String(), weave.legacy.weave.weave_types.NoneType()
        ),
        "differ": weave.legacy.weave.weave_types.union(
            weave.legacy.weave.weave_types.Number(), weave.legacy.weave.weave_types.String()
        ),
    }

    # Nullable type
    unioned = weave.legacy.weave.weave_types.union(
        weave.legacy.weave.weave_types.NoneType(),
        weave.legacy.weave.weave_types.TypedDict({"a": weave.legacy.weave.weave_types.String()}),
    )
    assert unioned.property_types == {
        "a": weave.legacy.weave.weave_types.union(
            weave.legacy.weave.weave_types.String(), weave.legacy.weave.weave_types.NoneType()
        )
    }


def test_typeof_node():
    n = weave.save(5)
    assert weave.type_of(n + 5) == types.Function({}, types.Number())


@dataclasses.dataclass(frozen=True)
class SublistType(types.Type):
    _base_type = types.List
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
        # Union Tagged Union
        (
            types.UnionType(
                types.NoneType(),
                TaggedValueType(
                    types.TypedDict({}), types.union(types.NoneType(), types.Number())
                ),
            ),
            TaggedValueType(types.TypedDict({}), types.Number()),
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
        # Union with multiple none-like members
        (
            types.union(
                types.NoneType(), TaggedValueType(types.TypedDict({}), types.NoneType())
            ),
            types.Invalid(),
        ),
    ],
)
def test_non_none(in_type, out_type):
    assert types.non_none(in_type) == out_type


def test_const_union_resolves_union():
    assert (
        types.Const(types.union(types.NoneType(), types.Number()), 5).val_type
        == types.Int()
    )


def test_floatint_merged():
    assert weave.type_of([1.0, 2.0]).object_type == types.Float()
    assert weave.type_of([1.0, 2]).object_type == types.Float()
    assert weave.type_of([1, 2]).object_type == types.Int()


def test_typetype():
    tt = weave.type_of(weave.types.TypedDict({"a": weave.types.Int()}))
    assert tt == weave.types.TypeType(
        attr_types={
            "not_required_keys": weave.types.List(types.String()),
            "property_types": weave.types.Dict(types.String(), types.TypeType()),
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


def test_union_of_typetype_can_be_compared_to_other():
    t = types.UnionType(types.NoneType(), types.TypeType())
    assert t == t


def test_assign_dict_to_typeddict():
    assert weave.types.TypedDict({}).assign_type(
        weave.types.Dict(weave.types.String(), weave.types.String())
    )


def test_type_of_empty_array_union():
    assert weave.type_of(
        [
            {"a": []},
            {"a": [1]},
        ]
    ) == weave.types.List(
        weave.types.TypedDict({"a": weave.types.List(weave.types.Int())})
    )


def test_type_hash():
    assert hash(types.NoneType()) == hash(types.NoneType())
    assert hash(types.List(types.Int())) == hash(types.List(types.Int()))
    assert hash(types.TypedDict({"a": types.Int()})) == hash(
        types.TypedDict({"a": types.Int()})
    )
    assert hash(types.UnionType(types.NoneType(), types.String())) == hash(
        types.UnionType(types.String(), types.NoneType())
    )


def test_tagged_value_flow():
    vt_1 = types.TypedDict({"a": types.Int()})
    tt_1 = types.TypedDict({"b": types.String()})
    t_1 = TaggedValueType(vt_1, tt_1)

    vt_2 = types.TypedDict({"c": types.Boolean()})
    tt_2 = types.TypedDict({"d": types.Float()})
    t_2 = TaggedValueType(vt_2, tt_2)

    ut = types.TypedDict({"e": types.Timestamp()})
    uv = types.union(t_1, t_2)

    tut = TaggedValueType(ut, uv)

    assert tut.members == [TaggedValueType(ut, t_1), TaggedValueType(ut, t_2)]
    assert tut.property_types == {
        "d": TaggedValueType(ut, types.optional(TaggedValueType(vt_2, types.Float()))),
        "b": TaggedValueType(ut, types.optional(TaggedValueType(vt_1, types.String()))),
    }

    row_type = types.TypedDict({"a": types.Int(), "b": types.String()})
    list_type = types.List(row_type)
    list_tag_type = types.TypedDict({"t_1": types.Boolean()})
    tagged_list_type = TaggedValueType(list_tag_type, list_type)

    row_type_2 = types.TypedDict({"c": types.Int(), "b": types.String()})
    list_type_2 = types.List(row_type_2)
    list_tag_type_2 = types.TypedDict({"t_2": types.Boolean()})
    tagged_list_type_2 = TaggedValueType(list_tag_type_2, list_type_2)

    union_type = types.union(tagged_list_type, tagged_list_type_2)
    list_of_unions = types.List(union_type)

    pts = list_of_unions.object_type.object_type.property_types

    assert pts["a"] == types.optional(TaggedValueType(list_tag_type, types.Int()))
    assert pts["b"] == types.union(
        TaggedValueType(list_tag_type, types.String()),
        TaggedValueType(list_tag_type_2, types.String()),
    )
    assert pts["c"] == types.optional(TaggedValueType(list_tag_type_2, types.Int()))


MERGE_CONSTS_TEST_CASES = [
    (
        types.TypedDict(
            {
                "a": types.Const(types.Int(), 1),
            },
        ),
        types.TypedDict(
            {
                "a": types.Const(types.Int(), 2),
            },
        ),
        types.TypedDict(
            {
                "a": types.UnionType(
                    types.Const(types.Int(), 1), types.Const(types.Int(), 2)
                )
            },
        ),
    ),
    (
        types.TypedDict(
            {
                "a": types.List(
                    types.UnionType(
                        types.Const(types.Int(), 1), types.Const(types.Int(), 2)
                    )
                ),
            },
        ),
        types.TypedDict(
            {
                "a": types.List(
                    types.UnionType(
                        types.Const(types.Int(), 1), types.Const(types.Int(), 3)
                    )
                ),
            },
        ),
        types.TypedDict(
            {
                "a": types.List(
                    types.UnionType(
                        types.Const(types.Int(), 1),
                        types.Const(types.Int(), 2),
                        types.Const(types.Int(), 3),
                    )
                )
            },
        ),
    ),
    (
        types.TypedDict(
            {"a": wbmedia.ImageArtifactFileRefType({"boxLayer1": [1, 2, 3]})},
        ),
        types.TypedDict(
            {"a": wbmedia.ImageArtifactFileRefType({"boxLayer1": [1, 3, 9]})},
        ),
        types.TypedDict(
            {"a": wbmedia.ImageArtifactFileRefType({"boxLayer1": [1, 2, 3, 9]})},
        ),
    ),
]


@pytest.mark.parametrize("t1, t2, expected", MERGE_CONSTS_TEST_CASES)
def test_merge_consts(t1, t2, expected):
    assert types.merge_types(t1, t2) == expected


def test_parse_const_type():
    assert types.parse_constliteral_type({"a": [1, 2, 3]}) == types.TypedDict(
        {
            "a": types.List(
                types.union(
                    types.Const(types.Int(), 1),
                    types.Const(types.Int(), 2),
                    types.Const(types.Int(), 3),
                )
            )
        }
    )


def test_init_image():
    image_ref_type = wbmedia.ImageArtifactFileRefType({"a": [1, 2, 3]})
    assert image_ref_type.boxLayers == types.TypedDict(
        {
            "a": types.List(
                types.union(
                    types.Const(types.Int(), 1),
                    types.Const(types.Int(), 2),
                    types.Const(types.Int(), 3),
                )
            )
        }
    )

    d = image_ref_type.to_dict()
    assert d == {
        "_base_type": {"type": "Object"},
        "_is_object": True,
        "boxLayers": {"a": [1, 2, 3]},
        "boxScoreKeys": [],
        "classMap": {},
        "maskLayers": {},
        "type": "image-file",
    }


def test_deserializes_single_member_union():
    # weave0 may produce these
    assert (
        types.TypeRegistry.type_from_dict({"members": ["int"], "type": "union"})
        == types.Int()
    )


def test_wbrun_not_assignable_to_weave_run():
    from weave.legacy.weave.ops_domain import wb_domain_types

    assert not weave.types.optional(wb_domain_types.Run().WeaveType()).assign_type(
        weave.types.RunType(
            inputs=weave.types.TypedDict(property_types={}),
            history=weave.types.List(object_type=weave.types.UnknownType()),
            output=weave.types.NoneType(),
        )
    )


def test_generic_object_type():
    t = types.ObjectType(id=types.String())
    assert t.assign_type(types.RunType(output=types.Int()))
    assert not t.assign_type(types.RefType())


def test_union_auto_execute():
    assert weave.types.optional(weave.types.Timestamp()).assign_type(
        weave.types.Function(output_type=weave.types.optional(weave.types.Timestamp()))
    )


def test_load_unknown_subobj_type():
    t = weave.types.TypeRegistry.type_from_dict(
        {
            "type": "typedDict",
            "propertyTypes": {"a": "int", "b": {"type": "some_unknown_type"}},
        }
    )
    assert isinstance(t, types.TypedDict)
    assert t.property_types["a"] == types.Int()
    assert t.property_types["b"] == types.UnknownType()
