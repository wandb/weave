from . import registry_mem
from . import op_def
from . import derive_op
from . import pyfunc_type_util


def op(
    input_type=None,
    output_type=None,
    refine_output_type=None,
    name=None,
    setter=None,
    render_info=None,
    pure=True,
):
    """Decorator for declaring an op.

    Decorated functions must be typed, either with Python types or by declaring
    input_type, output_type as arguments to op (Python types preferred).
    """

    def wrap(f):
        fq_op_name = name
        if fq_op_name is None:
            fq_op_name = "op-%s" % f.__name__
            # Don't use fully qualified names (which are URIs) for
            # now.
            # Ah crap this isn't right yet.
            # fq_op_name = op_def.fully_qualified_opname(f)

        weave_input_type = pyfunc_type_util.determine_input_type(f, input_type)
        weave_output_type = pyfunc_type_util.determine_output_type(f, output_type)

        op = op_def.OpDef(
            fq_op_name,
            weave_input_type,
            weave_output_type,
            f,
            refine_output_type=refine_output_type,
            setter=setter,
            render_info=render_info,
            pure=pure,
            _decl_locals=inspect.currentframe().f_back.f_locals,
        )

        op_version = registry_mem.memory_registry.register_op(op)

        # After we register the op, create any derived ops
        derive_op.derive_ops(op)

        return op_version

    return wrap
