import copy
import inspect
import typing

from . import graph
from . import registry_mem
from . import op_def
from . import storage
from . import errors
from . import op_args
from . import weave_types as types
from . import infer_types

py_type = type
from .decorator_type import type
from .decorator_class import weave_class


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
                # In the case that we have a callable weave_output_type, but no
                # refine type, then we need a way to tell TS what the return type is.
                # Here we define a custom refine type that calls the provided output_type
                # function. This is a bit of a hack, but it works. Notably, it operates
                # in the slower, value-space so we should think about optimizing in the future.
                if refine_output_type is not None:
                    registry_mem.memory_registry.register_op(
                        op_def.OpDef(
                            fq_op_name + "_refine_output_type",
                            weave_input_type,
                            infer_types.python_type_to_type(types.Type),
                            lambda **kwargs: weave_output_type(
                                {
                                    k: types.TypeRegistry.type_of(v)
                                    for k, v in kwargs.items()
                                }
                            ),
                        )
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


class Action:
    path: graph.Node  # TODO: we can linearize this, it shouldn't be a graph?
    fn: typing.Any
    args: tuple

    def __init__(self, path, fn, args):
        self.path = path
        self.fn = fn
        self.args = args

    def __repr__(self):
        return "<Action %s %s(%s)>" % (
            self.path,
            self.fn.__name__,
            ", ".join([s.__repr__() for s in self.args]),
        )


def _do_mutation_call(f, args, action=None):
    if action is None:
        arg_node0 = storage.get_obj_expr(storage.get_ref(args[0]))
        if arg_node0 is not None:
            action = Action(arg_node0, f, args[1:])
    res = f(*args)
    # if the op that produced us has setter, call it
    from_run = storage.get_obj_creator(storage._get_ref(args[0]))
    if from_run is not None:
        op_def = registry_mem.memory_registry.get_op(from_run._op_name)
        run_inputs = {
            name: storage.deref(input) for name, input in from_run._inputs.items()
        }
        if op_def.setter is not None:
            op_def.setter(*run_inputs.values(), res, action=action)
    return res


def mutation(f):
    def call(*args, **kwargs):
        action = kwargs.pop("action", None)
        if kwargs:
            args = list(kwargs.values())
        return _do_mutation_call(f, args, action=action)

    # Attach the signature so additional decorators (@op) can use it.
    call.sig = inspect.signature(f)
    return call
