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

    # merge nested dictionary types
    self_keys = set(self.property_types.keys())
    other_keys = set(other.property_types.keys())
    common_keys = self_keys.intersection(other_keys)

    for key in common_keys:
        self_property_type = self.property_types[key]
        other_property_type = other.property_types[key]
        if isinstance(self_property_type, types.TypedDict) and isinstance(
            other_property_type, types.TypedDict
        ):
            merged_dict_type = typeddict_merge_output_type(
                {
                    "self": self_property_type,
                    "other": other_property_type,
                }
            )

            property_types[key] = (
                types.TypedDict(
                    property_types=merged_dict_type.property_types,
                )
                if isinstance(merged_dict_type, types.TypedDict)
                else types.UnknownType()
            )

    return types.TypedDict(property_types=property_types)
