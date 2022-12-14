from .tagged_value_type import TaggedValueType
from ... import weave_types as types


def op_get_tag_type_resolver(obj_type: types.Type) -> types.Type:
    if isinstance(obj_type, TaggedValueType) or (
        isinstance(obj_type, types.Const)
        and isinstance(obj_type.val_type, TaggedValueType)
    ):
        return obj_type.tag
    else:
        return types.NoneType()


def op_make_type_tagged_resolver(
    obj_type: types.Type, tag_type: types.Type
) -> types.Type:
    if isinstance(tag_type, types.TypedDict):
        return TaggedValueType(tag_type, obj_type)
    else:
        return obj_type


def op_make_type_key_tag_resolver(
    obj_type: types.Type, key: str, tag_type: types.Type
) -> types.Type:
    tags = {key: tag_type}
    if isinstance(tag_type, TaggedValueType) and isinstance(
        tag_type.tag, types.TypedDict
    ):
        tags.update(tag_type.tag.property_types)
    return TaggedValueType(types.TypedDict(tags), obj_type)
