from . import tagging_op_logic
from ... import weave_types as types
from ... import decorator_op


@decorator_op.op(
    name="op_get_tag_type",
    input_type={
        "obj_type": types.TypeType(),
    },
    output_type=types.TypeType(),
)
def op_get_tag_type(obj_type):  # type: ignore
    return tagging_op_logic.op_get_tag_type_resolver(obj_type)


@decorator_op.op(
    name="op_make_type_tagged",
    input_type={
        "obj_type": types.TypeType(),
        "tag_type": types.TypeType(),
    },
    output_type=types.TypeType(),
)
def op_make_type_tagged(obj_type, tag_type):  # type: ignore
    return tagging_op_logic.op_make_type_tagged_resolver(obj_type)


@decorator_op.op(
    name="op_make_type_key_tag",
    input_type={
        "obj_type": types.TypeType(),
        "key": types.String(),
        "tag_type": types.TypeType(),
    },
    output_type=types.TypeType(),
)
def op_make_type_key_tag(obj_type, key, tag_type):  # type: ignore
    return tagging_op_logic.op_make_type_key_tag_resolver(obj_type, key, tag_type)
