import dataclasses
import typing

from . import op_def
from . import op_args
from . import graph
from . import errors
from . import weave_types as types
from . import weave_internal
from .ops_primitives import make_list, dict_


def op_to_weave_fn(opdef: op_def.OpDef) -> graph.Node:

    # TODO: remove this condition. we should be able to convert mutations to weave functions but
    # we need to figure out how to do it
    if opdef.is_mutation:
        raise errors.WeavifyError(
            f"Cannot derive weave function from mutation op {opdef.name}"
        )

    if opdef.name.startswith("mapped"):
        raise errors.WeavifyError("Cannot convert mapped op to weave_fn here")

    if opdef.name.startswith("Arrow"):
        raise errors.WeavifyError(
            "Refusing to convert op that is already defined on Arrow object to weave_fn"
        )

    if opdef.name.startswith("objectConstructor"):
        raise errors.WeavifyError(
            "Can't convert objectConstructor to weave_fn: %s" % opdef
        )

    # `merge` is a poison pill. It contains a {**dict1, **dict2} operation,
    # which, when dict[1/2] are nodes, never returns - it creates an infinite
    # loop. This will be true for any op def that contains a `**` operation
    # since `{**ops.dict_(a=1)}` will just hang forever.
    if opdef.name == "merge":
        raise errors.WeavifyError("Can't convert merge to weave_fn")

    # if is_base_op(opdef):
    #     raise errors.WeaveTypeError("Refusing to convert base op to weave_fn.")

    input_type = opdef.input_type
    if isinstance(input_type, op_args.OpVarArgs):
        raise errors.WeavifyError("Refusing to convert variadic op to weave_fn.")
    input_type = typing.cast(op_args.OpNamedArgs, input_type)

    if any(types.is_custom_type(t) for t in input_type.arg_types.values()):
        raise errors.WeavifyError("Can't weavify op with custom typed args")

    original_input_types = typing.cast(
        types.TypedDict, input_type.weave_type()
    ).property_types

    def weave_fn_body(*args: graph.VarNode) -> graph.Node:
        kwargs = {key: args[i] for i, key in enumerate(original_input_types)}
        result = opdef.resolve_fn(**kwargs)  # type: ignore
        return weavify_object(result)

    return weave_internal.define_fn(original_input_types, weave_fn_body).val


def weavify_object(obj: typing.Any) -> graph.Node:
    if isinstance(obj, graph.Node):
        return obj
    elif isinstance(obj, list):
        return make_list(**{str(i): weavify_object(o) for i, o in enumerate(obj)})
    elif isinstance(obj, dict):
        return dict_(**{i: weavify_object(o) for i, o in obj.items()})
    # this covers all weave created objects by @weave.type()
    elif dataclasses.is_dataclass(obj.__class__):
        return obj.__class__.constructor(
            dict_(
                **{
                    field.name: weavify_object(getattr(obj, field.name))
                    for field in dataclasses.fields(obj)
                }
            )
        )
    # bool needs to come first because int is a subclass of bool
    elif isinstance(obj, bool):
        return weave_internal.make_const_node(types.Boolean(), obj)
    elif isinstance(obj, int):
        return weave_internal.make_const_node(types.Int(), obj)
    elif isinstance(obj, float):
        return weave_internal.make_const_node(types.Float(), obj)
    elif isinstance(obj, str):
        return weave_internal.make_const_node(types.String(), obj)
    elif obj is None:
        return weave_internal.make_const_node(types.NoneType(), obj)
    else:
        raise errors.WeaveTypeError(f"Cannot weavify object of type {obj.__class__}")
