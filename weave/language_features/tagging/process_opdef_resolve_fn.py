"""
This file contains a single exported function `process_opdef_resolve_fn`. Techncailly,
this could have been implemented in `op_def.py`, but we want to keep all the tagging-related
logic in one place. Therefore, in op_def.py we import this function and call it to post-process
the result of the op_def's resolve_fn. 
"""

import typing

from .tagged_value_type import TaggedValueType

from ... import box
from ... import weave_types as types
from . import tag_store
from .opdef_util import get_first_arg, should_flow_tags, should_tag_op_def_outputs

if typing.TYPE_CHECKING:
    from ... import op_def as OpDef


# This function is responcible for post-processing the results of a resolve_fn.
# Specifically, it will take one of 3 actions:
# 1. If `_should_tag_op_def_outputs` is true, then it will tag the output with the input.
# 2. Else If `_should_flow_tags`, then it will flow the tags from the input to the output.
# 3. Else, it will just return the output.
def process_opdef_resolve_fn(
    op_def: "OpDef.OpDef",
    res: typing.Any,
    args: list[typing.Any],
    kwargs: dict[str, typing.Any],
) -> typing.Any:
    res = box.box(res)
    if should_tag_op_def_outputs(op_def):
        key, val = get_first_arg(op_def, args, kwargs)
        result_is_identity = id(val) == id(res)
        if not result_is_identity:
            if isinstance(res, types.Type):
                res = TaggedValueType(
                    types.TypedDict({key: types.TypeRegistry.type_of(val)}), res
                )
            else:
                tag_store.add_tags(res, {key: val})
    elif should_flow_tags(op_def):
        key, val = get_first_arg(op_def, args, kwargs)
        if tag_store.is_tagged(val):
            if isinstance(res, types.Type):
                if isinstance(val, TaggedValueType):
                    res = TaggedValueType(val.tag, res)
            else:
                tag_store.add_tags(res, tag_store.get_tags(val))
    return res
