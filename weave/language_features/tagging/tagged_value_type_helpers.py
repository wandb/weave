from . import tagged_value_type
from ... import weave_types as types


def push_down_tags_from_container_type_to_element_type(
    container_type: types.Type,
) -> types.Type:

    if not isinstance(container_type, tagged_value_type.TaggedValueType):
        return container_type

    if not types.List().assign_type(container_type):
        raise ValueError(
            f"push_down_tags: expected container_type to be a list, got {container_type}"
        )

    container_tag_type = container_type.tag
    container_value_type = container_type.value.object_type  # type: ignore
    if isinstance(container_type.object_type, tagged_value_type.TaggedValueType):
        new_tag_type = types.TypedDict(
            {
                **container_tag_type.property_types,
                **container_type.object_type.tag.property_types,  # type: ignore
            }
        )
    else:
        new_tag_type = container_tag_type
    new_inner_type = tagged_value_type.TaggedValueType(
        new_tag_type, container_value_type
    )
    container_outer_type = container_type.value.__class__
    return container_outer_type(new_inner_type)  # type: ignore


def is_tagged_value_type(t: types.Type) -> bool:
    return (
        isinstance(t, tagged_value_type.TaggedValueType)
        or isinstance(t, types.Const)
        and isinstance(t.val_type, tagged_value_type.TaggedValueType)
    )
