import typing

from ... import op_args
from ... import weave_types as types
from ... import decorator_op
from . import tagged_value_type
from . import tag_store

if typing.TYPE_CHECKING:
    from ... import op_def as OpDef


def make_tag_getter_op(
    tag_key: str,
    tag_type: types.Type = types.Any(),
    base_type: types.Type = types.Any(),
    op_name: typing.Optional[str] = None,
) -> "OpDef.OpDef":
    """Create an op that returns the value of a tag on a tagged value.

    Args:
        name: The name of the op.
        tag_key: The key of the tag to get.
        tag_type: The type of the tag to get.
        base_type: The type of the tagged value to get the tag from.

    Returns:
        The op.
    """
    # Uncomment below once we allow searching by type alone.
    # if tag_key is None and tag_type is None:
    #     raise ValueError("Must provide either tag_key or tag_type")
    if op_name is None:
        op_name = f"get_tag-{tag_key}"

    @decorator_op.op(  # type: ignore
        name=op_name,
        input_type={
            "obj": tagged_value_type.TaggedValueType(
                types.TypedDict({tag_key: tag_type}), base_type
            ),
        },
        output_type=lambda input_types: input_types["obj"].tag.property_types[tag_key],
    )
    def tag_getter_op(obj):  # type: ignore
        return tag_store.find_tag(obj, tag_key, tag_type)

    return tag_getter_op


# This is a heruistic that is used to determine if an op is a tag getter.
# In the future we might just have a single tag getter operation which
# would make this irrelevant or different.
def is_tag_getter(op: "OpDef.OpDef") -> bool:
    return _is_single_tag_getter(op) or _is_mapped_tag_getter(op)


def _is_single_tag_getter(op: "OpDef.OpDef") -> bool:
    return (
        op.name.startswith("tag-")
        or op.name.startswith("get_tag-")
        and isinstance(op.input_type, op_args.OpNamedArgs)
        and "obj" in op.input_type.arg_types
        and isinstance(
            op.input_type.arg_types["obj"], tagged_value_type.TaggedValueType
        )
    )


def _is_mapped_tag_getter(op: "OpDef.OpDef") -> bool:
    return (
        op.name.startswith("mapped_tag-")
        or op.name.startswith("mapped_get_tag-")
        and isinstance(op.input_type, op_args.OpNamedArgs)
        and "obj" in op.input_type.arg_types
        and isinstance(op.input_type.arg_types["obj"], types.List)
        and isinstance(
            op.input_type.arg_types["obj"].object_type,
            tagged_value_type.TaggedValueType,
        )
    )
