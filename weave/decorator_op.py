import copy
import inspect
import typing

from . import registry_mem
from . import op_def
from . import errors
from . import op_args
from . import weave_types as types
from . import infer_types


def _create_args_from_op_input_type(input_type):
    if isinstance(input_type, op_args.OpArgs):
        return input_type
    if not isinstance(input_type, dict):
        raise errors.WeaveDefinitionError("input_type must be OpArgs or a dict")
    for k, v in input_type.items():
        if not isinstance(v, types.Type) and not callable(v):
            raise errors.WeaveDefinitionError(
                "input_type must be dict[str, Type] but %s is %s" % (k, v)
            )
    return op_args.OpNamedArgs(input_type)


def is_op(f):
    return hasattr(f, "op_def")


def get_signature(f):
    if hasattr(f, "sig"):
        return f.sig
    return inspect.signature(f)


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
        if hasattr(f, "sig"):
            type_hints = {
                k: p.annotation
                for k, p in f.sig.parameters.items()
                if p.annotation is not p.empty
            }
        else:
            type_hints = typing.get_type_hints(f)

        ##### Input type processing

        python_input_type = copy.copy(type_hints)
        if "return" in python_input_type:
            python_input_type.pop("return")

        declared_input_type = input_type
        if declared_input_type is None:
            declared_input_type = {}
        weave_input_type = _create_args_from_op_input_type(declared_input_type)

        if weave_input_type.kind == op_args.OpArgs.NAMED_ARGS:
            arg_names = get_signature(f).parameters.keys()

            # validate there aren't extra declared Weave types
            weave_type_extra_arg_names = set(weave_input_type.arg_types.keys()) - set(
                arg_names
            )
            if weave_type_extra_arg_names:
                raise errors.WeaveDefinitionError(
                    "Weave Types declared for non-existent args: %s."
                    % weave_type_extra_arg_names
                )

            arg_types = {}

            # iterate through function args in order. The function determines
            # the order of arg_types, which is relied on everywhere.
            for input_name in arg_names:
                python_type = python_input_type.get(input_name)
                existing_weave_type = weave_input_type.arg_types.get(input_name)
                if python_type is not None:
                    inferred_type = infer_types.python_type_to_type(python_type)
                    if inferred_type == types.UnknownType():
                        raise errors.WeaveDefinitionError(
                            "Weave Type could not be determined from Python type (%s) for arg: %s."
                            % (python_type, input_name)
                        )
                    if existing_weave_type and existing_weave_type != inferred_type:
                        raise errors.WeaveDefinitionError(
                            "Python type (%s) and Weave Type (%s) declared for arg: %s. Remove one of them to fix."
                            % (inferred_type, existing_weave_type, input_name)
                        )
                    arg_types[input_name] = inferred_type
                elif existing_weave_type:
                    arg_types[input_name] = existing_weave_type
                else:
                    arg_types[input_name] = types.UnknownType()

            # validate there aren't missing Weave types
            unknown_type_args = set(
                arg_name
                for arg_name, at in arg_types.items()
                if at == types.UnknownType()
            )
            weave_type_missing_arg_names = unknown_type_args - {"self", "_run"}
            if weave_type_missing_arg_names:
                raise errors.WeaveDefinitionError(
                    "Missing Weave Types for args: %s." % weave_type_missing_arg_names
                )

            weave_input_type = op_args.OpNamedArgs(arg_types)
        else:
            # TODO: no validation here...
            pass

        fq_op_name = name
        if fq_op_name is None:
            fq_op_name = "op-%s" % f.__name__
            # Don't use fully qualified names (which are URIs) for
            # now.
            # Ah crap this isn't right yet.
            # fq_op_name = op_def.fully_qualified_opname(f)

        ##### Output type processing

        python_return_type = type_hints.get("return")
        if python_return_type is None:
            inferred_output_type = types.UnknownType()
        else:
            inferred_output_type = infer_types.python_type_to_type(python_return_type)
            if inferred_output_type == types.UnknownType():
                raise errors.WeaveDefinitionError(
                    "Could not infer Weave Type from declared Python return type: %s"
                    % python_return_type
                )

        weave_output_type = output_type
        if weave_output_type is None:
            # weave output type is not declared, use type inferred from Python
            weave_output_type = inferred_output_type
        else:
            # Weave output_type was declared. Ensure compatibility with Python type.
            if callable(weave_output_type):
                if inferred_output_type != types.UnknownType():
                    raise errors.WeaveDefinitionError(
                        "output_type is function but Python return type also declared. This is not yet supported"
                    )
            elif (
                inferred_output_type != types.UnknownType()
                and weave_output_type.assign_type(inferred_output_type)
                == types.Invalid()
            ):
                raise errors.WeaveDefinitionError(
                    "Python return type not assignable to declared Weave output_type: %s !-> %s"
                    % (inferred_output_type, weave_output_type)
                )
        if not callable(weave_output_type) and weave_output_type == types.UnknownType():
            raise errors.WeaveDefinitionError(
                "Op's return type must be declared: %s" % f
            )

        op = op_def.OpDef(
            fq_op_name,
            weave_input_type,
            weave_output_type,
            f,
            refine_output_type=refine_output_type,
            setter=setter,
            render_info=render_info,
            pure=pure,
        )

        op_version = registry_mem.memory_registry.register_op(op)
        return op_version

    return wrap
