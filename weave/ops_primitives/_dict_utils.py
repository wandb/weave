import typing
from weave import weave_types as types


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
    self: types.TypedDict
    other: types.TypedDict


def typeddict_merge_output_type(
    input_types: MergeInputTypes,
) -> typing.Union[types.TypedDict, types.UnknownType]:
    self = input_types["self"]
    other = input_types["other"]
    if not isinstance(self, types.TypedDict) or not isinstance(other, types.TypedDict):
        return types.UnknownType()

    # create property types without merging nested dictionary types (for now)
    property_types = {
        **self.property_types,
        **other.property_types,
    }

    return types.TypedDict(property_types=property_types)
