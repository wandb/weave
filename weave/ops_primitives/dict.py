import typing
from ._dict_utils import typeddict_pick_output_type
from ..api import op, weave_class, OpVarArgs
from .. import weave_types as types
from ._dict_utils import tag_aware_dict_val_for_escaped_key
from ..language_features.tagging import tagged_value_type

# @op(
#     name='pick',
#     input_type={
#         'obj': types.TypedDict({}),
#         'key': types.String()},
#     output_type=types.Any())
# def pick(obj, key):
#     # TODO: is this how we want to delegate?
#     if hasattr(obj, 'pick'):
#         return obj.pick(key)
#     if isinstance(obj, list):
#         return [o.get(key) for o in obj]
#     return obj.get(key)

# TODO: make it so we can still call the underlying op pick!
#     or make it so we can declare pick on each item that has it?
#    The latter is much nicer if we can make it work I think.
#      should be easy, we can look up op based on which object its being
#      called on
# Then figure out how to do array/mapped ops...


def is_const_union_of_type(type_, of_type):
    if not isinstance(type_, types.UnionType):
        return False
    return all(
        isinstance(m, types.Const) and m.val_type == of_type for m in type_.members
    )


# TODO: in this PR, this was important for making scenario compare work.
#    - but Tim did some similar fix for Union Types, so I need to revisit
# def typeddict_pick_output_type(input_types):
#     if isinstance(input_types["self"], types.UnionType):
#         return types.union(
#             *(
#                 typeddict_pick_output_type({"self": m, "key": input_types["key"]})
#                 for m in input_types["self"].members
#             )
#         )
#     property_types = input_types["self"].property_types
#     if is_const_union_of_type(input_types["key"], types.String()):
#         member_types = []
#         for m in input_types["key"].members:
#             prop_type = property_types.get(m.val)
#             if prop_type is None:
#                 member_types.append(types.NoneType())
#             else:
#                 member_types.append(prop_type)
#         return types.union(*member_types)

#     if not isinstance(input_types["key"], types.Const):
#         return types.union(*list(property_types.values()))
#     key = input_types["key"].val
#     output_type = property_types.get(key)
#     if output_type is None:
#         # TODO: we hack this to types.Number() for now! This is relied
#         # on by tests because readcsv() doesn't properly return a full
#         # type right now. Super janky
#         return types.Number()
#     return output_type


@weave_class(weave_type=types.TypedDict)
class TypedDict:
    def __setitem__(self, k, v, action=None):
        dict.__setitem__(self, k, v)
        return self

    @op(
        setter=__setitem__,
        input_type={"self": types.TypedDict({}), "key": types.optional(types.String())},
        output_type=typeddict_pick_output_type,
    )
    def pick(self, key):
        return tag_aware_dict_val_for_escaped_key(self, key)

    @op(
        output_type=lambda input_type: types.List(
            types.union(
                *(
                    types.Const(types.String(), k)
                    for k in input_type["self"].property_types.keys()
                )
            )
        )
    )
    def keys(self):
        return list(self.keys())

    @op(
        name="merge",
        input_type={"lhs": types.TypedDict({}), "rhs": types.TypedDict({})},
        output_type=lambda input_types: types.TypedDict(
            {**input_types["lhs"].property_types, **input_types["rhs"].property_types}
        ),
    )
    def merge(lhs, rhs):
        return {**lhs, **rhs}

    @op(
        name="typedDict-values",
        output_type=lambda input_types: types.List(
            types.union(*input_types["self"].property_types.values())
        ),
    )
    def values(self):
        return self.values()

    __getitem__ = pick


def dict_return_type(input_types):
    # Discard Const types!
    # TODO: this is probably not really ideal. We lose a lot of information here.
    # But we don't handle unions very well in Weave1 right now, so this makes
    # developing panel composition stuff easier.
    res = {}
    for k, v in input_types.items():
        if isinstance(v, types.Const):
            res[k] = v.val_type
        else:
            res[k] = v
    return types.TypedDict(res)


@op(
    name="dict",
    input_type=OpVarArgs(types.Any()),
    # output_type=lambda input_types: types.TypedDict(input_types),
    output_type=dict_return_type,
)
def dict_(**d):
    return d


def _keytypes_resovler(
    weave_type: types.Type,
) -> list[dict[str, typing.Union[str, types.Type]]]:
    res: list[dict[str, typing.Union[str, types.Type]]] = []
    if isinstance(weave_type, types.TypedDict):
        for k, v in weave_type.property_types.items():
            res.append(
                {
                    "key": k,
                    "type": v,
                }
            )
    elif isinstance(weave_type, tagged_value_type.TaggedValueType):
        return _keytypes_resovler(weave_type.value)
    return res


@op(
    name="object-keytypes",
    input_type={
        "obj": types.TypedDict({}),
    },
    output_type=types.List(
        types.TypedDict(
            {
                "key": types.String(),
                "type": types.TypeType(),
            }
        )
    ),
)
def object_keytypes(obj):
    # Unlike Weave0, we don't have the type information of inputs, so
    # unfortunately we have to figure out the types using the data....
    weave_type = types.TypeRegistry.type_of(obj)
    return _keytypes_resovler(weave_type)
