import typing

from ... import weave_types as types
from ... import decorator_op
from . import tagged_value_type
from . import tag_store
from ...ops_arrow.list_ import ArrowWeaveList, ArrowWeaveListType

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
                types.TypedDict({tag_key: types.optional(tag_type)}), base_type
            ),
        },
        output_type=lambda input_types: input_types["obj"].tag.property_types.get(
            tag_key, types.NoneType()
        ),
    )
    def tag_getter_op(obj):  # type: ignore
        return tag_store.find_tag(obj, tag_key, tag_type)

    # This is the vectorized version of the tag getter specifically for
    # ArrowWeaveList. We have discussed the possibility of having a single tag
    # getter op and a single vectorized tag getter op which can handle any tag
    # requested, but in the meantime, this matches the Weave0 pattern.
    @decorator_op.op(  # type: ignore
        name=f"ArrowWeaveList_{op_name}",
        input_type={
            "obj": ArrowWeaveListType(
                tagged_value_type.TaggedValueType(
                    types.TypedDict({tag_key: types.optional(tag_type)}), base_type
                ),
            )
        },
        output_type=lambda input_types: ArrowWeaveListType(
            input_types["obj"].object_type.tag.property_types[tag_key]
        ),
    )
    def awl_tag_getter_op(obj):  # type: ignore
        return ArrowWeaveList(
            obj._arrow_data.field("_tag").field(tag_key),
            obj.object_type.tag.property_types[tag_key],
            obj._artifact,
        )

    tag_getter_op._gets_tag_by_name = tag_key
    awl_tag_getter_op._gets_tag_by_name = tag_key

    return tag_getter_op
