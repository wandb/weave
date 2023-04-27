import copy
import inspect
import typing

from . import errors
from . import op_args
from . import weave_types as types
from . import infer_types


def determine_input_type(
    pyfunc: typing.Callable,
    expected_input_type: typing.Optional[
        typing.Union[op_args.OpArgs, typing.Dict[str, types.Type]]
    ] = None,
    # TODO: I really don't like this boolean flag here.
    allow_unknowns: bool = False,
) -> op_args.OpArgs:
    python_input_type = _get_type_hints(pyfunc)
    if "return" in python_input_type:
        python_input_type.pop("return")

    declared_input_type = expected_input_type
    if declared_input_type is None:
        declared_input_type = {}
    weave_input_type = _create_args_from_op_input_type(declared_input_type)

    if isinstance(weave_input_type, op_args.OpNamedArgs):
        sig = get_signature(pyfunc)
        sig_params = sig.parameters
        arg_names = sig_params.keys()
        var_arg_params = [
            param
            for param in sig_params.values()
            if param.kind == param.VAR_POSITIONAL or param.kind == param.VAR_KEYWORD
        ]
        is_var_args = len(var_arg_params) > 0

        # validate there aren't extra declared Weave types
        if not is_var_args:
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
            param = sig_params[input_name]
            if (
                param.kind == param.VAR_POSITIONAL
                or param.kind == param.VAR_KEYWORD
                or input_name == "_run"
            ):
                continue

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

        if is_var_args:
            # Add any remaining weave types if we have var args
            for key, t in weave_input_type.arg_types.items():
                if key not in arg_names:
                    arg_types[key] = t

        # validate there aren't missing Weave types
        unknown_type_args = set(
            arg_name for arg_name, at in arg_types.items() if at == types.UnknownType()
        )
        weave_type_missing_arg_names = unknown_type_args - {"self"}
        if weave_type_missing_arg_names and not allow_unknowns:
            raise errors.WeaveDefinitionError(
                "Missing Weave Types for args: %s." % weave_type_missing_arg_names
            )

        weave_input_type = op_args.OpNamedArgs(arg_types)
    else:
        # TODO: no validation here...
        pass

    return weave_input_type


def determine_output_type(
    pyfunc: typing.Callable,
    expected_output_type: typing.Optional[
        typing.Union[types.Type, typing.Callable[..., types.Type]]
    ] = None,
    allow_unknowns: bool = False,
) -> typing.Union[types.Type, typing.Callable[..., types.Type]]:
    type_hints = _get_type_hints(pyfunc)
    python_return_type = type_hints.get("return")
    inferred_output_type: types.Type
    if python_return_type is None:
        inferred_output_type = types.UnknownType()
    else:
        inferred_output_type = infer_types.python_type_to_type(python_return_type)
        if inferred_output_type == types.UnknownType():
            raise errors.WeaveDefinitionError(
                "Could not infer Weave Type from declared Python return type: %s"
                % python_return_type
            )

    weave_output_type = expected_output_type
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
            and not weave_output_type.assign_type(inferred_output_type)
        ):
            raise errors.WeaveDefinitionError(
                "Python return type not assignable to declared Weave output_type: %s !-> %s"
                % (inferred_output_type, weave_output_type)
            )
    if (
        not callable(weave_output_type)
        and weave_output_type == types.UnknownType()
        and not allow_unknowns
    ):
        raise errors.WeaveDefinitionError(
            "Op's return type must be declared: %s" % pyfunc
        )

    return weave_output_type


def get_signature(pyfunc: typing.Callable) -> inspect.Signature:
    if hasattr(pyfunc, "sig"):
        return pyfunc.sig  # type: ignore
    return inspect.signature(pyfunc)


def _create_args_from_op_input_type(
    input_type: typing.Union[op_args.OpArgs, typing.Dict[str, types.Type]]
) -> op_args.OpArgs:
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


def _get_type_hints(pyfunc: typing.Callable) -> dict[str, typing.Any]:
    if hasattr(pyfunc, "sig"):
        type_hints = {
            k: p.annotation
            for k, p in pyfunc.sig.parameters.items()  # type: ignore
            if p.annotation is not p.empty
        }
    else:
        type_hints = typing.get_type_hints(pyfunc)
    return type_hints
