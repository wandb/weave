import inspect

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
    _op_def_class=op_def.OpDef,
    *,  # Marks the rest of the arguments as keyword-only.
    plugins=None
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

        op = _op_def_class(
            fq_op_name,
            weave_input_type,
            weave_output_type,
            f,
            refine_output_type=refine_output_type,
            setter=setter,
            render_info=render_info,
            pure=pure,
            plugins=plugins,
            _decl_locals=inspect.currentframe().f_back.f_locals,
        )

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


def arrow_op(
    input_type=None,
    output_type=None,
    refine_output_type=None,
    name=None,
    setter=None,
    render_info=None,
    pure=True,
):
    """An arrow op is an op that should obey element-based tag-flow map rules. An arrow op must

    1) Have a first arg that is an ArrowWeaveList.
    2) Output an ArrowWeaveList with the same shape as (1)
    3) Each element of the output should represent a mapped transform of the input

    In these cases, element tags from (1) are automatically propagated to each element of (2).

    NOTE: we dont actually need this decorator to do this, we can do it with type inference alone.
    This will be added in a future pr, and this decorator will be removed.
    """

    def make_output_type(input_types):
        from .ops_arrow import ArrowWeaveListType, tagged_value_type

        original_output_type: ArrowWeaveListType
        if callable(output_type):
            original_output_type = output_type(input_types)
        else:
            original_output_type = output_type

        first_input_type_name = next(k for k in input_types)
        first_input_type = input_types[first_input_type_name]

        if not callable(output_type) and isinstance(
            first_input_type.object_type, tagged_value_type.TaggedValueType
        ):
            return ArrowWeaveListType(
                tagged_value_type.TaggedValueType(
                    first_input_type.object_type.tag, original_output_type.object_type
                )
            )

        return original_output_type

    # TODO(DG): handle reading input and output types from function signature
    return op(
        input_type=input_type,
        output_type=make_output_type,
        refine_output_type=refine_output_type,
        name=name,
        setter=setter,
        render_info=render_info,
        pure=pure,
        _op_def_class=op_def.AutoTagHandlingArrowOpDef,
    )
