import inspect
import typing

from . import context_state, derive_op, op_args, op_def, pyfunc_type_util, registry_mem
from . import weave_types as types

if typing.TYPE_CHECKING:
    from weave.gql_op_plugin import GqlOpPlugin


def op(
    _func=None,
    /,
    *,
    input_type: pyfunc_type_util.MaybeInputTypeType = None,
    output_type: pyfunc_type_util.MaybeOutputTypeType = None,
    refine_output_type: typing.Optional[op_def.OpDef] = None,
    name: typing.Optional[str] = None,
    setter: typing.Optional[typing.Callable] = None,
    render_info: typing.Optional[dict] = None,
    hidden: bool = False,
    pure: bool = True,
    _op_def_class: type[op_def.OpDef] = op_def.OpDef,
    plugins: typing.Optional[dict[str, "GqlOpPlugin"]] = None,
    mutation: bool = False,
    weavify: bool = False,
):
    """Decorator for declaring an op."""

    def wrap(func):
        allow_unknowns = not context_state._loading_built_ins.get()
        weave_input_type = pyfunc_type_util.determine_input_type(func, input_type, allow_unknowns=allow_unknowns)
        weave_output_type = pyfunc_type_util.determine_output_type(func, output_type, allow_unknowns=allow_unknowns)

        fq_op_name = name
        if fq_op_name is None:
            op_prefix = "op"
            fq_op_name = f"{op_prefix}-{func.__name__}"

        op = _op_def_class(
            fq_op_name,
            weave_input_type,
            weave_output_type,
            func,
            refine_output_type=refine_output_type,
            setter=setter,
            render_info=render_info,
            hidden=hidden,
            pure=pure,
            plugins=plugins,
            mutation=mutation,
        )
        if weavify:
            from .weavify import op_to_weave_fn

            op.weave_fn = op_to_weave_fn(op)

        op_version = registry_mem.memory_registry.register_op(op)

        if op.location is None:
            derive_op.derive_ops(op)

        return op_version

    if callable(_func):
        # The decorator was used as @op without parentheses.
        return wrap(_func)
    else:
        # The decorator was used as @op(...) with parentheses.
        # Return a new decorator that will call 'decorator' with the function later.
        return wrap
