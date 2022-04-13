import copy
import inspect
import typing

from . import graph
from . import registry_mem
from . import op_def
from . import storage
from . import lazy
from . import errors
from . import op_args
from . import weave_types as types
from . import infer_types


def weave_class(weave_type):
    def wrap(target):
        # add self type to input_types if its not already defined.
        for _, method in inspect.getmembers(target):
            if is_op(method):
                self_type = method.op_def.input_type.arg_types.get("self")
                if self_type is not None and self_type == types.UnknownType():
                    method.op_def.input_type.arg_types["self"] = weave_type()

        weave_type.NodeMethodsClass = target
        return target

    return wrap


def _create_args_from_op_input_type(input_type):
    if isinstance(input_type, op_args.OpArgs):
        return input_type
    if not isinstance(input_type, dict):
        raise errors.WeaveDefinitionError("input_type must be OpArgs or a dict")
    for k, v in input_type.items():
        if not isinstance(v, types.Type):
            raise errors.WeaveDefinitionError(
                "input_type must be dict[str, Type] but %s is %s" % (k, v)
            )
    return op_args.OpNamedArgs(input_type)


def is_op(f):
    return hasattr(f, "op_def")


def op(
    input_type=None,
    output_type=None,
    name=None,
    setter=None,
    render_info=None,
    pure=True,
):
    """Decorator for declaring an op.

    Decorated functions must be typed, either with Python types or by declaring
    input_type, output_Type as arguments to op (Python types preferred).
    """

    def wrap(f):
        type_hints = typing.get_type_hints(f)

        ##### Input type processing

        python_input_type = copy.copy(type_hints)
        if "return" in python_input_type:
            python_input_type.pop("return")
        inferred_input_type = {
            input_name: infer_types.python_type_to_type(input_type)
            for input_name, input_type in python_input_type.items()
        }
        weave_input_type = input_type
        if weave_input_type is None:
            # No weave declared input_type, so use the inferred_type
            for arg_name in inspect.signature(f).parameters.keys():
                if arg_name == "self":
                    # Special case if the arg is called self. We allow it to be Unknown.
                    # We'll detect its type later when the weave_class() decorator runs.
                    # (method decorators run before the class is created, then the class decorators
                    # run)
                    inferred_input_type["self"] = types.UnknownType()
                elif arg_name not in inferred_input_type:
                    raise errors.WeaveDefinitionError(
                        "type declaration missing for arg: %s" % arg_name
                    )
                elif inferred_input_type[arg_name] == types.UnknownType():
                    raise errors.WeaveDefinitionError(
                        "Weave type not registered for python type: %s"
                        % python_input_type[arg_name]
                    )
            weave_input_type = op_args.OpNamedArgs(inferred_input_type)

            # TODO: Detect that all input types are declared!
        else:
            weave_input_type = _create_args_from_op_input_type(weave_input_type)
            # Weave input_type was declared. Ensure compatibility with Python type.
            if inferred_input_type:
                if weave_input_type.kind == op_args.OpArgs.NAMED_ARGS:
                    arg_types = weave_input_type.arg_types
                    if set(inferred_input_type.keys()) != set(arg_types.keys()):
                        raise errors.WeaveDefinitionError(
                            "Weave input_type length must match op function arglist length"
                        )

                    for input_name, inferred_type in inferred_input_type.items():
                        if (
                            arg_types[input_name].assign_type(inferred_type)
                            == types.Invalid()
                        ):
                            raise errors.WeaveDefinitionError(
                                "Python type incompatible with with Weave type for arg: %s"
                                % input_name
                            )
                else:
                    # TODO: handle varargs!
                    pass

        ##### Output type processing

        python_return_type = type_hints.get("return")
        if python_return_type is None:
            inferred_output_type = types.UnknownType()
        else:
            inferred_output_type = infer_types.python_type_to_type(python_return_type)
            if inferred_output_type == types.UnknownType():
                raise errors.WeaveDefinitionError(
                    "Could not infer Weave Type from declared Python return type"
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

        fq_op_name = name
        if fq_op_name is None:
            fq_op_name = "op-%s" % f.__name__
            # Don't use fully qualified names (which are URIs) for
            # now.
            # Ah crap this isn't right yet.
            # fq_op_name = op_def.fully_qualified_opname(f)

        op = op_def.OpDef(
            fq_op_name,
            weave_input_type,
            weave_output_type,
            f,
            setter=setter,
            render_info=render_info,
            pure=pure,
        )

        op_version = registry_mem.memory_registry.register_op(op)
        return op_version.call_fn

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
