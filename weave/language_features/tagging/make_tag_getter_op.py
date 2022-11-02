import typing

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
        output_type=base_type,
    )
    def tag_getter_op(obj):  # type: ignore
        return tag_store.find_tag(obj, tag_key, tag_type)

    return tag_getter_op
