import typing
from .. import weave_types as types
from .. import errors


def typeddict_pick_output_type(input_types):
    property_types = input_types["self"].property_types
    if not isinstance(input_types["key"], types.Const):
        return types.union(*property_types.values())
    key = input_types["key"].val
    output_type = property_types.get(key)
    if output_type is None:
        return types.NoneType()
    return output_type


class MergeInputTypes(typing.TypedDict):
    self: typing.Union[types.TypedDict, types.UnionType, types.NoneType]
    other: types.TypedDict


def typeddict_merge_output_type(
    input_types: MergeInputTypes,
) -> typing.Union[types.TypedDict, types.UnionType, types.NoneType, types.UnknownType]:
    self = input_types["self"]
    other = input_types["other"]
    self_ok = types.UnionType(types.TypedDict({}), types.NoneType()).assign_type(self)
    if not self_ok or not isinstance(other, types.TypedDict):
        return types.UnknownType()

    # create property types without merging nested dictionary types (for now)
    if isinstance(self, types.TypedDict):
        property_types = {
            **self.property_types,
            **other.property_types,
        }

        return types.TypedDict(property_types=property_types)
    elif isinstance(self, types.UnionType):
        if not self.is_simple_nullable():
            return types.UnknownType()
        non_null_member = types.non_none(self)
        return types.UnionType(
            typeddict_merge_output_type(
                {"self": typing.cast(types.TypedDict, non_null_member), "other": other}
            ),
            types.NoneType(),
        )
    elif isinstance(self, types.NoneType):
        return types.NoneType()
    else:
        raise errors.WeaveTypeError(f"Unhandled types for dict merge: {self}, {other}")
