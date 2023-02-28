from ... import op_args
import typing

from ... import weave_types as types
from . import tagged_value_type

if typing.TYPE_CHECKING:
    from ... import op_def as OpDef


def is_tag_getter(op: "OpDef.OpDef") -> bool:
    return op._gets_tag_by_name is not None
