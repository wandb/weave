"""
This file contains a single exported function `process_opdef_resolve_fn`. Technically,
this could have been implemented in `op_def.py`, but we want to keep all the tagging-related
logic in one place. Therefore, in op_def.py we import this function and call it to post-process
the result of the op_def's resolve_fn.
"""

import typing
import typing_extensions
import pyarrow as pa
from pyarrow import compute as pc

from .tagged_value_type import TaggedValueType
from ... import box
from ... import weave_types as types
from . import tag_store
from .opdef_util import (
    get_first_arg,
    should_flow_tags,
    should_tag_op_def_outputs,
)

if typing.TYPE_CHECKING:
    from ... import op_def as OpDef


def _is_tagged_value(val: types.Type) -> typing_extensions.TypeGuard[TaggedValueType]:
    return isinstance(val, TaggedValueType)


def _is_optional_tagged_value(
    val: types.Type,
) -> typing_extensions.TypeGuard[types.UnionType]:
    return types.is_optional(val) and isinstance(types.non_none(val), TaggedValueType)


def _strip_tags(val: typing.Any) -> typing.Any:
    from ...ops_arrow import ArrowWeaveList

    if isinstance(val, ArrowWeaveList):
        if _is_tagged_value(val.object_type):
            return ArrowWeaveList(
                val._arrow_data.field("_value"),
                val.object_type.value,
                val._artifact,
            )

        elif _is_optional_tagged_value(val.object_type):
            return ArrowWeaveList(
                val._arrow_data.field("_value"),
                typing.cast(TaggedValueType, types.non_none(val.object_type)).value,
                val._artifact,
            )
    return val


# here we strip the tags from each element of an arrow weave list and create a
# new arrow weave list that contains just the untagged values. We then pass that
# to the op resolver. On we get the result back, we re-apply the tags we stripped
# previously
def propagate_arrow_tags(
    op_def: "OpDef.OpDef",
    resolve_fn: typing.Callable,
    args: list[typing.Any],
    kwargs: dict[str, typing.Any],
) -> typing.Any:
    from ...ops_arrow.arrow_tags import awl_add_arrow_tags
    from ...ops_arrow import ArrowWeaveList

    tag_type: typing.Optional[types.Type]

    _, first_arg_val = get_first_arg(op_def, args, kwargs)
    first_arg_val = typing.cast(ArrowWeaveList, first_arg_val)

    is_optional_tagged = False
    if _is_tagged_value(first_arg_val.object_type):
        first_arg_tags = first_arg_val._arrow_data.field("_tag")
        tag_type = first_arg_val.object_type.tag
    elif _is_optional_tagged_value(first_arg_val.object_type):
        first_arg_tags = first_arg_val._arrow_data.field("_tag")
        tag_type = typing.cast(
            TaggedValueType, types.non_none(first_arg_val.object_type)
        ).tag
        is_optional_tagged = True
    else:
        first_arg_tags = None
        tag_type = None

    tag_stripped_args: list[typing.Any] = []
    tag_stripped_kwargs: dict[str, typing.Any] = {}

    for arg in args:
        tag_stripped_args.append(_strip_tags(arg))

    for key, val in kwargs.items():
        tag_stripped_kwargs[key] = _strip_tags(val)

    res = resolve_fn(*tag_stripped_args, **tag_stripped_kwargs)

    # rewrap tags
    if first_arg_tags and tag_type:
        res = awl_add_arrow_tags(
            res,
            first_arg_tags,
            tag_type,
        )

        if is_optional_tagged:
            mask = pc.invert(pc.is_valid(first_arg_val._arrow_data))
            new_arrow_data = pa.StructArray.from_arrays(
                [res._arrow_data.field("_tag"), res._arrow_data.field("_value")],
                ["_tag", "_value"],
                mask=mask,
            )

            res = ArrowWeaveList(
                new_arrow_data,
                types.optional(res.object_type),
                res._artifact,
            )

    return res


def flow_tags(
    first_input: typing.Any,
    output: typing.Any,
    give_precedence_to_existing_tags: bool = False,
) -> typing.Any:
    if tag_store.is_tagged(first_input):
        tag_dict = tag_store.get_tags(first_input)
        if isinstance(output, types.Type):
            if len(tag_dict.keys()) == 0:
                return output
            tag_type = types.TypeRegistry.type_of(tag_dict)
            assert isinstance(tag_type, types.TypedDict)
            return TaggedValueType(tag_type, output)
        return tag_store.add_tags(
            output,
            tag_dict,
            give_precedence_to_existing_tags=give_precedence_to_existing_tags,
        )
    return output


# This function is responsible for post-processing the results of a resolve_fn.
# Specifically, it will take one of 3 actions:
# 1. If `_should_tag_op_def_outputs` is true, then it will tag the output with the input.
# 2. Else If `_should_flow_tags`, then it will flow the tags from the input to the output.
# 3. Else, it will just return the output.
def process_opdef_resolve_fn(
    op_def: "OpDef.OpDef",
    resolve_fn: typing.Callable,
    args: list[typing.Any],
    kwargs: dict[str, typing.Any],
) -> typing.Any:
    if op_def.op_def_is_auto_tag_handling_arrow_op():
        res = propagate_arrow_tags(op_def, resolve_fn, args, kwargs)

        # TODO(DG): implement this for Table, ChunkedArray, etc.
        if isinstance(res._arrow_data, pa.Array) and res._arrow_data.null_count > 0:
            res.object_type = types.optional(res.object_type)

    else:
        res = resolve_fn(*args, **kwargs)

    res = box.box(res)
    if should_tag_op_def_outputs(op_def):
        key, val = get_first_arg(op_def, args, kwargs)
        result_is_identity = id(val) == id(res)
        if not result_is_identity:
            tag_dict = {key: val}
            if isinstance(res, types.Type):
                tag_type = types.TypeRegistry.type_of(tag_dict)
                assert isinstance(tag_type, types.TypedDict)
                return TaggedValueType(tag_type, res)
            return tag_store.add_tags(res, tag_dict)
    elif should_flow_tags(op_def):
        key, val = get_first_arg(op_def, args, kwargs)
        return flow_tags(val, res, give_precedence_to_existing_tags=True)
    return res
