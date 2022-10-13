import typing
from . import weave_types as types
from . import artifacts_local
from . import graph

if typing.TYPE_CHECKING:
    from . import op_def as OpDef


def process_opdef_resolution(
    op_def: "OpDef.OpDef",
    res: typing.Any,
    args: list[typing.Any],
    kwargs: dict[str, typing.Any],
) -> typing.Any:
    # Exception list
    if isinstance(res, artifacts_local.Artifact):
        return res
    if isinstance(res, graph.Node):
        return res
    # I am here, just returning empty tagged value to ensure I can handle all cases
    return types.TaggedValue({}, res)
    named_args = op_def.input_type.named_args()
    params = op_def.input_type.create_param_dict(args, kwargs)
    if (
        len(named_args) > 0
        and len(params) > 0
        and not types.TaggedType(types.TypedDict({}), types.Any()).assign_type(
            named_args[0].type
        )
    ):
        first_arg_val = params[named_args[0].name]
        if first_arg_val != res:
            tags = {}
            if isinstance(first_arg_val, types.TaggedValue):
                tags = first_arg_val._tag
            tags[named_args[0].name] = first_arg_val
            return types.TaggedValue(tags, res)
    return res
