import typing
from .. import weave_types as types
from .. import errors
from ..language_features.tagging import tag_store, tagged_value_type
from .. import box


def typeddict_pick_output_type(input_types):
    property_types = input_types["self"].property_types
    if not isinstance(input_types["key"], types.Const):
        return types.union(*property_types.values())
    key = input_types["key"].val
    output_type = _tag_aware_dict_or_list_type_for_path(
        input_types["self"], split_escaped_string(key)
    )
    return output_type


def tag_aware_dict_val_for_escaped_key(
    obj: dict, key: typing.Optional[str]
) -> typing.Any:
    if key == None:
        return None
    return _any_val_for_path(obj, split_escaped_string(key))


class MergeInputTypes(typing.TypedDict):
    self: typing.Union[types.TypedDict, types.UnionType, types.NoneType]
    other: types.TypedDict


def typeddict_merge_output_type(
    input_types: MergeInputTypes,
) -> typing.Union[types.TypedDict, types.UnionType, types.NoneType, types.UnknownType]:
    self: types.Type = input_types["self"]
    other: types.Type = input_types["other"]

    if isinstance(self, types.Const):
        self = self.val_type

    if isinstance(other, types.Const):
        other = other.val_type

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


# Re-implementation of helpers2.py
def unescape_dots(s: str) -> str:
    return s.replace("\\.", ".")


def escape_dots(s: str) -> str:
    return s.replace(".", "\\.")


def split_escaped_string(s: typing.Optional[str]) -> list[str]:
    # splits a string on dots, but ignores dots that are escaped
    # e.g. "a.b.c" -> ["a", "b", "c"]
    # e.g. "a\\.b.c" -> ["a.b", "c"]
    if s is None:
        return []
    placeholder = "___DOT___"
    s = s.replace("\\.", placeholder)
    parts = s.split(".")
    parts = [p.replace(placeholder, ".") for p in parts]
    return parts


def _val_tag_wrapper(val: typing.Any) -> typing.Callable[[typing.Any], typing.Any]:
    tags = None
    if tag_store.is_tagged(val):
        tags = tag_store.get_tags(val)

    def wrapper(res: typing.Any) -> typing.Any:
        if tags is not None:
            return tag_store.add_tags(box.box(res), tags)
        else:
            return res

    return wrapper


def _any_val_for_path(val: typing.Any, path: list[str]) -> typing.Any:
    tag_wrapper = _val_tag_wrapper(val)
    if len(path) == 0:
        return None
    key = path[0]
    next_path = path[1:]
    if isinstance(val, list) and key == "*":
        if len(next_path) == 0:
            return val
        else:
            return tag_wrapper([_any_val_for_path(item, next_path) for item in val])
    elif isinstance(val, dict):
        return _dict_val_for_path(val, path)
    else:
        return None


def _dict_val_for_path(val: dict, path: list[str]) -> typing.Any:
    tag_wrapper = _val_tag_wrapper(val)
    if len(path) == 0:
        return None
    key = path[0]
    next_path = path[1:]
    if key == "*":
        return tag_wrapper(
            {
                sub_key: _any_val_for_path(sub_val, next_path)
                for sub_key, sub_val in val.items()
            }
        )
    if key not in val:
        return None
    key_val = val.get(key)
    if len(next_path) == 0:
        res = key_val
    else:
        res = _any_val_for_path(key_val, next_path)
    return tag_wrapper(res)


def _type_tag_wrapper(
    type: types.Type,
) -> typing.Tuple[typing.Callable[[types.Type], types.Type], types.Type]:
    tags = None
    inner_type = type
    if isinstance(type, tagged_value_type.TaggedValueType):
        tags = type.tag
        inner_type = type.value

    def wrapper(res: typing.Any) -> typing.Any:
        if tags is not None:
            return tagged_value_type.TaggedValueType(tags, res)
        else:
            return res

    return wrapper, inner_type


def _tag_aware_dict_or_list_type_for_path(
    type: types.Type, path: list[str]
) -> types.Type:
    if isinstance(type, types.Const):
        type = type.val_type
    tag_wrapper, inner_type = _type_tag_wrapper(type)
    if len(path) == 0:
        return types.NoneType()
    if isinstance(inner_type, types.UnionType):
        return tag_wrapper(
            types.union(
                *[
                    _tag_aware_dict_or_list_type_for_path(mem_type, path)
                    for mem_type in inner_type.members
                ]
            )
        )
    if not (
        isinstance(inner_type, types.List) or isinstance(inner_type, types.TypedDict)
    ):
        return types.NoneType()
    key = path[0]
    next_path = path[1:]
    if isinstance(inner_type, types.List) and key == "*":
        if len(next_path) == 0:
            return type
        else:
            return tag_wrapper(
                types.List(
                    _tag_aware_dict_or_list_type_for_path(
                        inner_type.object_type, next_path
                    )
                )
            )
    elif isinstance(inner_type, types.TypedDict):
        return _dict_type_for_path(type, path)
    else:
        return types.NoneType()


def _dict_type_for_path(type: types.Type, path: list[str]) -> types.Type:
    tag_wrapper, inner_type = _type_tag_wrapper(type)
    if len(path) == 0:
        return types.NoneType()
    if not isinstance(inner_type, types.TypedDict):
        return types.NoneType()
    prop_types = inner_type.property_types
    key = path[0]
    next_path = path[1:]
    if key == "*":
        return tag_wrapper(
            types.TypedDict(
                {
                    sub_key: _tag_aware_dict_or_list_type_for_path(sub_val, next_path)
                    for sub_key, sub_val in prop_types.items()
                }
            )
        )
    if key not in prop_types:
        return types.NoneType()
    key_val = typing.cast(types.Type, prop_types.get(key))
    if len(next_path) == 0:
        res = key_val
    else:
        res = _tag_aware_dict_or_list_type_for_path(key_val, next_path)

    return tag_wrapper(res)
