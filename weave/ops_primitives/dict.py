from ..api import op, weave_class, mutation, OpVarArgs
from .. import weave_types as types

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


def typeddict_pick_output_type(input_types):
    if isinstance(input_types["self"], types.UnionType):
        return types.union(
            *(
                typeddict_pick_output_type({"self": m, "key": input_types["key"]})
                for m in input_types["self"].members
            )
        )
    property_types = input_types["self"].property_types
    if is_const_union_of_type(input_types["key"], types.String()):
        member_types = []
        for m in input_types["key"].members:
            prop_type = property_types.get(m.val)
            if prop_type is None:
                member_types.append(types.NoneType())
            else:
                member_types.append(prop_type)
        return types.union(*member_types)

    if not isinstance(input_types["key"], types.Const):
        return types.union(*list(property_types.values()))
    key = input_types["key"].val
    output_type = property_types.get(key)
    if output_type is None:
        # TODO: we hack this to types.Number() for now! This is relied
        # on by tests because readcsv() doesn't properly return a full
        # type right now. Super janky
        return types.Number()
    return output_type


# TODO: type dict v dict


@weave_class(weave_type=types.TypedDict)
class TypedDict:
    @mutation
    def __setitem__(self, k, v):
        dict.__setitem__(self, k, v)
        return self

    @op(
        setter=__setitem__,
        input_type={"self": types.TypedDict({}), "key": types.String()},
        output_type=typeddict_pick_output_type,
    )
    def pick(self, key):
        if not isinstance(self, dict):
            # won't need this when we fix type-checking, but for now it
            # surfaces an error
            # TODO: totally not right, need to figure out mapped ops
            return self.pick(key)
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return None

    @op(
        output_type=lambda input_type: types.List(
            types.UnionType(
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
        output_type=types.TypedDict({}),
    )
    def merge(lhs, rhs):
        return {**lhs, **rhs}

    __getitem__ = pick


@weave_class(weave_type=types.Dict)
class Dict(dict):
    @mutation
    def __setitem__(self, k, v):
        dict.__setitem__(self, k, v)
        return self

    @op(
        setter=__setitem__,
        input_type={
            "self": types.Dict(types.String(), types.Any()),
            "key": types.String(),
        },
        output_type=lambda input_types: input_types["self"].object_type,
    )
    def pick(self, key):
        if not isinstance(self, dict):
            # won't need this when we fix type-checking, but for now it
            # surfaces an error
            # TODO: totally not right, need to figure out mappped ops
            return self.pick(key)
        return self.get(key)

    __getitem__ = pick


# @weave_class(weave_type=types.TypedDict)
# class TypedDict(dict):
#     @op(
#         name='pick',
#         input_type={
#             'obj': types.TypedDict({}),
#             'key': types.String()
#         },
#         output_type=types.Any())
#     def __getitem__(obj, key):
#         print('OBJ', type(obj))
#         return super(TypedDict, obj).__getitem__(key)


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
