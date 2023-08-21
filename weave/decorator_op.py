import inspect

from . import registry_mem
from . import op_def
from . import op_args
from . import derive_op
from . import weave_types as types
from . import pyfunc_type_util


def op(
    input_type=None,
    output_type=None,
    refine_output_type=None,
    name=None,
    setter=None,
    render_info=None,
    hidden=False,
    pure=True,
    _op_def_class=op_def.OpDef,
    *,  # Marks the rest of the arguments as keyword-only.
    plugins=None,
    mutation=False,
    # If True, the op will be weavified, ie it's resolver will be stored as a Weave
    # op graph. The compile node_ops pass will expand the node to the weavified
    # version, instead of executing the original python resolver body.
    weavify=False,
):
    """Decorator for declaring an op.

    Decorated functions must be typed, either with Python types or by declaring
    input_type, output_type as arguments to op (Python types preferred).
    """

    def wrap(f):
        weave_input_type = pyfunc_type_util.determine_input_type(f, input_type)
        weave_output_type = pyfunc_type_util.determine_output_type(f, output_type)

        fq_op_name = name
        if fq_op_name is None:
            op_prefix = "op"

            # This would be a much nicer: automatically use first type name.
            # But what about Unions? I'm not going to solve in this PR.
            # TODO: implement this.
            # if (
            #     isinstance(weave_input_type, op_args.OpNamedArgs)
            #     and weave_input_type.arg_types
            # ):
            #     arg_type0 = next(iter(weave_input_type.arg_types.values()))
            #     if arg_type0 != types.UnknownType():
            #         op_prefix = arg_type0.name

            fq_op_name = f"{op_prefix}-{f.__name__}"

        op = _op_def_class(
            fq_op_name,
            weave_input_type,
            weave_output_type,
            f,
            refine_output_type=refine_output_type,
            setter=setter,
            render_info=render_info,
            hidden=hidden,
            pure=pure,
            plugins=plugins,
            mutation=mutation,
            _decl_locals=inspect.currentframe().f_back.f_locals,
        )
        if weavify:
            from .weavify import op_to_weave_fn

            op.weave_fn = op_to_weave_fn(op)

        op_version = registry_mem.memory_registry.register_op(op)

        # After we register the op, create any derived ops

        # If op.location is set, then its a custom (non-builtin op). We don't
        # derive custom ops for now, as the derive code doesn't do the right thing.
        # The op name is the location/uri for custom ops, and the derive code doesn't
        # fix that up. So we end up double registering ops in WeaveJS which breaks
        # everything.
        # TODO: fix so we get mappability for custom (ecosystem) ops!
        if op.location is None:
            derive_op.derive_ops(op)

        return op_version

    return wrap
