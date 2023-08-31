import typing

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


def unwrap_tags(
    t: types.Type,
) -> typing.Tuple[types.Type, typing.Callable[[types.Type], types.Type]]:
    # unwrap the tags from a type until we hit the first untagged type.
    # return the untagged type and return a function that rewraps it or
    # another type in the original tag tree.

    # see test_tagging.py::test_unwrap_rewrap_tags for examples.

    def wrap_outer(unwrapped: types.Type) -> types.Type:
        if isinstance(t, tagged_value_type.TaggedValueType):
            return tagged_value_type.TaggedValueType(t.tag, unwrapped)
        return unwrapped

    if isinstance(t, tagged_value_type.TaggedValueType):
        unwrapped, wrap_inner = unwrap_tags(t.value)
    else:
        unwrapped, wrap_inner = t, lambda x: x

    return unwrapped, lambda unwrapped_inner: wrap_outer(wrap_inner(unwrapped_inner))
