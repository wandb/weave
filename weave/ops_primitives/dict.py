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


def typeddict_pick_output_type(input_types):
    if not isinstance(input_types["key"], types.Const):
        return types.UnknownType()
    key = input_types["key"].val
    property_types = input_types["obj"].property_types
    output_type = property_types.get(key)
    if output_type is None:
        # TODO is types.Invalid() right?
        # return types.Invalid()
        # TODO: we hack this to types.Number() for now as a demonstration
        # but its really Invalid until we do an async refineType (not
        # yet supported in Weave Python)
        return types.Number()
    return output_type


# TODO: type dict v dict


@weave_class(weave_type=types.TypedDict)
class TypedDict(dict):
    @mutation
    def __setitem__(self, k, v):
        dict.__setitem__(self, k, v)
        return self

    @op(
        setter=__setitem__,
        input_type={"obj": types.TypedDict(types.Any()), "key": types.String()},
        output_type=typeddict_pick_output_type,
    )
    def pick(obj, key):
        if not isinstance(obj, dict):
            # won't need this when we fix type-checking, but for now it
            # surfaces an error
            # TODO: totally not right, need to figure out mappped ops
            return obj.pick(key)
        return dict.__getitem__(obj, key)

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
            "obj": types.Dict(types.String(), types.Any()),
            "key": types.String(),
        },
        output_type=lambda input_types: input_types["obj"].value_type,
    )
    def pick(obj, key):
        if not isinstance(obj, dict):
            # won't need this when we fix type-checking, but for now it
            # surfaces an error
            # TODO: totally not right, need to figure out mappped ops
            return obj.pick(key)
        return obj.get(key)

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


@op(
    name="dict",
    input_type=OpVarArgs(types.Any()),
    output_type=types.TypedDict({}),
)
def dict_(**d):
    return d


@op(
    name="merge",
    input_type={"lhs": types.TypedDict({}), "rhs": types.TypedDict({})},
    output_type=types.TypedDict({}),
)
def merge(lhs, rhs):
    return {**lhs, **rhs}
