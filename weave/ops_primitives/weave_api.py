import typing
import time

from weave.graph import Node
from ..api import op, mutation, weave_class
from .. import weave_types as types
from .. import errors
from .. import storage
from .. import registry_mem
from .. import weave_internal
from .. import trace
from .. import refs
from .. import uris
from .. import graph
from .. import artifacts_local


@weave_class(weave_type=types.RefType)
class RefNodeMethods:
    @op(output_type=lambda input_type: input_type["self"].object_type)
    def get(self):
        return storage.deref(self)


# Hmm... This returns the same obj, not a ref anymore
# TODO: is this what we want?
@op(
    name="save",
    input_type={"obj": types.Any(), "name": types.String()},
    output_type=lambda input_types: input_types["obj"],
)
def save(obj, name):
    ref = storage.save(obj, name=name)
    return ref.obj


def usedby_output_type(op_name: str) -> types.Type:
    op_def = registry_mem.memory_registry.get_op(op_name)

    if callable(op_def.output_type):
        # We can certainly fix this. But this would be a really cool case for
        # type variables. If this op outputs an output type with variables,
        # we could include them in the returned type here.
        # TODO: Fix
        raise errors.WeaveInternalError(
            "asking for used_by of op with callable output type not yet supported"
        )

    return types.List(
        types.RunType(inputs=op_def.input_type.weave_type(), output=op_def.output_type)
    )


def used_by_callable_output_type(input_type) -> types.Type:
    if not isinstance(input_type["op_name"], types.Const):
        return types.List(types.RunType())
    op_name = input_type["op_name"].val
    return usedby_output_type(op_name)


@op(render_info={"type": "function"})
def usedby_refine_output_type(obj: typing.Any, op_name: str) -> types.Type:
    return usedby_output_type(op_name)


@op(
    pure=False,
    output_type=used_by_callable_output_type,
    refine_output_type=usedby_refine_output_type,
)
def used_by(obj: typing.Any, op_name: str):
    ref = storage.get_ref(obj)
    if ref is None:
        return []
    res = trace.used_by(ref, op_name)
    return res


@op()
def call_op(name: str) -> Node[types.Any]:
    return weave_internal.make_output_node(types.Any(), name, {})


@op()
def objects_refine_output_type(
    of_type: types.Type, alias: str, timestamp: int
) -> types.Type:
    return types.List(types.RefType(of_type))


@op(
    render_info={"type": "function"},
    output_type=lambda input_type: types.List(input_type["of_type"]),
    refine_output_type=objects_refine_output_type,
    # Not impure now that we have the cache-busting timestamp arg
    # pure=False,
)
# Timestamp is a way for us to force cache this, but also
# be able to bust the cache.
# TODO: Think about this pattern
def objects(of_type: types.Type, alias: str, timestamp: int):
    return storage.objects(of_type, alias)


# TODO: used_by, created_by, and change them to use filter instead
#    to get filter output type right, I'll have to implement using refineOutputType
#    for now. We can optimize by moving this to the type system a little later.
# Then make a cool UI


def op_get_return_type(uri):
    return refs.Ref.from_str(uri).type


def op_get_return_type_from_inputs(inputs):
    return op_get_return_type(inputs["uri"].val)


@op(name="getReturnType", input_type={"uri": types.String()}, output_type=types.Type())
def get_returntype(uri):
    return op_get_return_type(uri)


@mutation
def _save(name, obj):

    obj_uri = uris.WeaveURI.parse(name)

    # Clear the ref, otherwise save will immediately return
    # the result instead of saving the mutated result
    storage.clear_ref(obj)
    storage.save(obj, name=obj_uri.full_name)


@op(
    pure=False,
    setter=_save,
    name="get",
    input_type={"uri": types.String()},
    output_type=op_get_return_type_from_inputs,
)
def get(uri):
    return storage.get(uri)


@mutation
def execute_setter(node, value):
    if isinstance(node, graph.ConstNode):
        return graph.ConstNode(node.type, value)
    else:
        # TODO: The OutputNode code path needs to do the mutation
        #     on node, instead of going back up whatever constructed
        #     Node
        raise errors.WeaveInternalError(
            "Execute setter path not implemented for ", node
        )


@op(
    # TODO: purity is a function of arguments in this special case.
    # E.g. if argument is "3 + 1", executing it is pure. If this matters
    # in practice, we can just hardcode in the engine.
    pure=False,
    setter=execute_setter,
    name="execute",
    input_type={"node": types.Function({}, types.Any())},
    output_type=lambda input_type: input_type["node"].output_type,
)
def execute(node):
    return weave_internal.use(node)


@weave_class(weave_type=types.Function)
class FunctionOps:
    @op(
        output_type=lambda input_type: input_type["self"].output_type,
    )
    def __call__(self, arg1: typing.Any):
        arg1_node = weave_internal.make_const_node(
            types.TypeRegistry.type_of(arg1), arg1
        )
        called = weave_internal.better_call_fn(self, arg1_node)
        return weave_internal.use(called)


@weave_class(weave_type=types.RunType)
class Run:
    # NOTE: the mutations here are unused, only used by test currently.
    # shows how we can implement the run API entirely on top of Weave objects,
    # but we're not using this internally so probably best to remove.
    @op(
        name="run-setstate",
        input_type={
            "state": types.RUN_STATE_TYPE,
        },
        # can't return run because then we'll think this is an async op!
        output_type=types.Invalid(),
    )
    @mutation
    def set_state(self, state):
        self.state = state
        return self

    @op(
        name="run-print",
        # can't return run because then we'll think this is an async op!
        output_type=types.Invalid(),
    )
    @mutation
    def print_(self, s: str):
        # print("PRINT s", s)
        self.prints.append(s)  # type: ignore
        return self

    @op(
        name="run-log",
        # can't return run because then we'll think this is an async op!
        output_type=types.Invalid(),
    )
    @mutation
    def log(self, v: typing.Any):
        self.history.append(v)  # type: ignore
        return self

    @mutation
    def set_inputs(self, v: typing.Any):
        self.inputs = v
        return self

    @op(
        name="run-setoutput",
        output_type=types.Invalid(),
    )
    @mutation
    def set_output(self, v: typing.Any):
        # Force the output to be a ref.
        # TODO: this is probably not the right place to do this.
        if not isinstance(v, storage.Ref):
            v = storage.save(v)
        self.output = v
        return self

    @op(
        name="run-await",
        output_type=lambda input_types: input_types["self"].output,
    )
    def await_final_output(self):
        sleep_mult = 1
        while self.state == "pending" or self.state == "running":
            sleep_time = 0.1 * sleep_mult
            if sleep_time > 3:
                sleep_time = 3
            sleep_mult *= 1.3
            time.sleep(sleep_time)

            # TODO: this should support full URIS instead of hard coding
            uri = uris.WeaveLocalArtifactURI.make_uri(
                artifacts_local.local_artifact_dir(), f"run-{self.id}", "latest"
            )
            self = weave_internal.use(get(uri))

        return self.output
