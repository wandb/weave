import inspect
import typing

from . import graph
from . import registry_mem
from . import storage
from . import lazy


def weave_class(weave_type):
    def wrap(target):
        weave_type.NodeMethodsClass = target
        return target

    return wrap


def op(input_type, output_type, name=None, setter=None, render_info=None, pure=True):
    """Decorator for declaring an op."""

    def wrap(f):
        fq_op_name = name
        if fq_op_name is None:
            fq_op_name = registry_mem.fully_qualified_opname(f)

        lazy_call = lazy.make_lazy_call(f, fq_op_name, input_type, output_type)
        lazy_call.is_weave = True

        registry_mem.memory_registry.register_op(
            registry_mem.OpDef(
                fq_op_name,
                input_type,
                output_type,
                lazy_call,
                f,
                setter=setter,
                render_info=render_info,
                pure=pure,
            )
        )

        return lazy_call

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
