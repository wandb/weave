from ... import op_args
import typing

from ... import weave_types as types
from . import tagged_value_type

if typing.TYPE_CHECKING:
    from ... import op_def as OpDef

# This is a heuristic that is used to determine if an op is a tag getter.
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
