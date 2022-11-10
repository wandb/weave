from weave.language_features.tagging.tagged_value_type import TaggedValueType
from ... import weave_types as types
from ... import decorator_op


@decorator_op.op(
    name="op_get_tag_type",
    input_type={
        "obj_type": types.Type(),
    },
    output_type=types.Type(),
)
def op_get_tag_type(obj_type):  # type: ignore
    if isinstance(obj_type, TaggedValueType):
        return obj_type.tag
    else:
        return types.NoneType()


@decorator_op.op(
    name="op_make_type_tagged",
    input_type={
        "obj_type": types.Type(),
        "tag_type": types.Type(),
    },
    output_type=types.Type(),
)
def op_make_type_tagged(obj_type, tag_type):  # type: ignore
    if isinstance(tag_type, types.TypedDict):
        return TaggedValueType(tag_type, obj_type)
    else:
        return obj_type


@decorator_op.op(
    name="op_make_type_key_tag",
    input_type={
        "obj_type": types.Type(),
        "key": types.String(),
        "tag_type": types.Type(),
    },
    output_type=types.Type(),
)
def op_make_type_key_tag(obj_type, key, tag_type):  # type: ignore
    if isinstance(tag_type, types.TypedDict):
        return TaggedValueType(tag_type, types.TypedDict({key: obj_type}))
    else:
        return obj_type
