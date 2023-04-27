import dataclasses
import typing

from . import val_const
from . import op_args
from . import graph
from . import errors
from . import weave_types as types
from . import weave_internal

if typing.TYPE_CHECKING:
    from . import op_def


def verify_weave_fn_is_valid(op: "op_def.OpDef", weavified: graph.Node) -> None:

    constituent_ops = typing.cast(
        list[graph.OutputNode],
        graph.filter_nodes_top_level(
            [weavified], lambda n: isinstance(n, graph.OutputNode)
        ),
    )
    output_nodes_disjoint = all([n.from_op.name != op.name for n in constituent_ops])

    if not output_nodes_disjoint:
        raise errors.WeavifyError(
            f"Weavified version of {op.name} contains a call to itself"
        )


def op_to_weave_fn(opdef: "op_def.OpDef") -> graph.Node:

    if opdef.name.startswith("mapped"):
        raise errors.WeavifyError("Cannot convert mapped op to weave_fn here")

    if opdef.name.startswith("Arrow"):
        raise errors.WeavifyError(
            "Refusing to convert op that is already defined on Arrow object to weave_fn"
        )

    if opdef._gets_tag_by_name != None:
        # This happens in test_wb_tables.py::test_join_group_combo. We fail to find the
        # vectorized version because the op is generated in the test and is not a built-in
        raise errors.WeavifyError(
            "Not weavifying tag op. We should already have a vectorized version!"
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

    fn = weave_internal.define_fn(original_input_types, weave_fn_body).val
    verify_weave_fn_is_valid(opdef, fn)

    return fn


def weavify_object(obj: typing.Any) -> graph.Node:
    from .ops_primitives import make_list, dict_

    if isinstance(obj, graph.Node):
        return obj
    elif isinstance(obj, val_const.Const):
        return weave_internal.make_const_node(
            types.Const(types.TypeRegistry.type_of(obj.val), obj.val), obj.val
        )
    elif isinstance(obj, list):
        return make_list(**{str(i): weavify_object(o) for i, o in enumerate(obj)})
    elif isinstance(obj, dict):
        return dict_(**{i: weavify_object(o) for i, o in obj.items()})

    try:
        return obj.__class__.constructor(
            **{
                field.name: weavify_object(getattr(obj, field.name))
                for field in dataclasses.fields(obj)
            }
        )
    except AttributeError:
        pass
    return weave_internal.make_const_node(types.TypeRegistry.type_of(obj), obj)
