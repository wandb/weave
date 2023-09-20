import typing

from ... import weave_types as types
from ... import decorator_op
from . import tagged_value_type
from . import tag_store
from ...ops_arrow.list_ import ArrowWeaveList, ArrowWeaveListType
from ...ops_arrow import arrow_tags

from ... import box

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
        output_type=lambda input_types: tagged_value_type.TaggedValueType(
            input_types["obj"].tag,
            input_types["obj"].tag.property_types.get(tag_key, types.NoneType()),
        ),
    )
    def tag_getter_op(obj):  # type: ignore
        untagged_result = tag_store.find_tag(obj, tag_key, tag_type)
        tags = tag_store.get_tags(obj)
        return tag_store.add_tags(box.box(untagged_result), tags)

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
            tagged_value_type.TaggedValueType(
                input_types["obj"].object_type.tag,
                input_types["obj"].object_type.tag.property_types[tag_key],
            )
        ),
    )
    def awl_tag_getter_op(obj):  # type: ignore
        key_type = obj.object_type.tag.property_types[tag_key]

        raw = ArrowWeaveList(
            obj._arrow_data.field("_tag").field(tag_key), key_type, obj._artifact
        )
        tags = obj._arrow_data.field("_tag")
        return arrow_tags.awl_add_arrow_tags(raw, tags, obj.object_type.tag)

    tag_getter_op._gets_tag_by_name = tag_key
    awl_tag_getter_op._gets_tag_by_name = tag_key

    return tag_getter_op
