import typing

from ... import weave_types as types
from . import tagged_value_type

if typing.TYPE_CHECKING:
    from ... import op_def as OpDef


# Determines if the op_def should ftag the output with the input. Currently, this is true
# as long as the op does not consume tags and the input of the op is an ObjectType. This
# may evolve over time.
def should_tag_op_def_outputs(op_def: "OpDef.OpDef") -> bool:
    named_args = op_def.input_type.named_args()
    return (
        should_flow_tags(op_def)
        # NOTICE: For now, we only autotag with sublcasses of ObjectType that
        # are named Test*, plus ProjectType and RunType.
        # Uncomment this during advanced testing to ensure tags work in the general cases
        and (
            (
                isinstance(named_args[0].type, types.ObjectType)
                and named_args[0].type.name.startswith("_Test")
            )
            or named_args[0].type.__class__.__name__ in ["projectType", "runType"]
        )
    )


# Determines if the op_def should flow tags from the input to the output. Currently,
# we assume yes, unless the op_def consumes a tag. This may evolve over time
def should_flow_tags(op_def: "OpDef.OpDef") -> bool:
    named_args = op_def.input_type.named_args()
    return (
        not op_def_consumes_tags(op_def)
        and len(named_args) > 0
        and not isinstance(named_args[0].type, types.Function)
        and not op_def.name.endswith("dropTags")
    )


# Helper function to determine if the op_def consumes a tag
def op_def_consumes_tags(op_def: "OpDef.OpDef") -> bool:
    named_args = op_def.input_type.named_args()
    return len(named_args) > 0 and tagged_value_type.TaggedValueType(
        types.TypedDict({}), types.Any()
    ).assign_type(named_args[0].type)


# Helper function to get the first argument of the op_def
def get_first_arg(
    op_def: "OpDef.OpDef", args: list[typing.Any], kwargs: dict[str, typing.Any]
) -> typing.Tuple[str, typing.Any]:
    params = op_def.input_type.create_param_dict(args, kwargs)
    key = list(params.keys())[0]
    return (key, params[key])
