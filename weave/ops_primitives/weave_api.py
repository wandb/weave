import typing
import time

from weave.graph import Node
from ..api import op, weave_class, mutation
from .. import weave_types as types
from .. import errors
from .. import storage
from .. import registry_mem
from .. import weave_internal
from .. import trace
from .. import ref_base
from .. import uris
from .. import graph
from .. import artifact_local
from .. import compile
from .. import runs
from .. import artifact_fs
from .. import artifact_wandb


def is_hexadecimal(s):
    """
    Returns True if the input string s is a hexadecimal value, False otherwise.
    """
    return all(c.isdigit() or c.isalpha() for c in s) and all(
        c in "0123456789abcdefABCDEF" for c in s
    )


@weave_class(weave_type=types.RefType)
class RefNodeMethods:
    @op(output_type=lambda input_type: input_type["self"].object_type)
    def get(self):
        return storage.deref(self)


# Hmm... This returns the same obj, not a ref anymore
# TODO: is this what we want?
@op(
    name="save",
    output_type=lambda input_types: input_types["obj"],
)
def save(obj: typing.Any, name: typing.Optional[str]):
    ref = storage.save(obj, name=name)
    return ref.obj


# TODO: This should not be a separate op.
# save above should return a ref. But some tests depend on it returning an object,
# which I didn't bother fixing yet.
@op(
    name="save_to_ref",
    output_type=types.RefType(),
    hidden=True,
)
def save_to_ref(obj: typing.Any, name: typing.Optional[str]):
    ref = storage.save(obj, name=name)
    return ref


def usedby_output_type(op_name: str) -> types.Type:
    op_def = registry_mem.memory_registry.get_op(op_name)

    if not callable(op_def.output_type):
        ot = op_def.output_type
    else:
        ot = op_def.concrete_output_type
        if isinstance(ot, types.UnknownType):
            # We can certainly fix this. But this would be a really cool case for
            # type variables. If this op outputs an output type with variables,
            # we could include them in the returned type here.
            # TODO: Fix
            raise errors.WeaveInternalError(
                "asking for used_by of op with callable output type not yet supported"
            )

    return types.List(types.RunType(inputs=op_def.input_type.weave_type(), output=ot))


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


def objects_output_type(input_type):
    if not isinstance(input_type["of_type"], types.Const):
        ref_obj_type = types.TypeType()
    else:
        ref_obj_type = input_type["of_type"].val

    return types.List(types.RefType(ref_obj_type))


@op(
    render_info={"type": "function"},
    output_type=objects_output_type,
    refine_output_type=objects_refine_output_type,
    # Not impure now that we have the cache-busting timestamp arg
    # pure=False,
)
# Timestamp is a way for us to force cache this, but also
# be able to bust the cache.
# TODO: Think about this pattern
def objects(of_type: types.Type, alias: str, timestamp: int):
    return storage.objects(of_type, alias)


# Return all local artifacts
# TODO: this is a placeholder used for loading dashboards. We won't really want to load
# all of them!
@op(render_info={"type": "function"})
def local_artifacts() -> list[artifact_local.LocalArtifact]:
    return storage.local_artifacts()


# TODO: used_by, created_by, and change them to use filter instead
#    to get filter output type right, I'll have to implement using refineOutputType
#    for now. We can optimize by moving this to the type system a little later.
# Then make a cool UI


def op_get_return_type(uri):
    ref = ref_base.Ref.from_str(uri)
    if not ref.is_saved:
        return types.NoneType()
    return ref.type


def get_const_val(list_type_or_node):
    if isinstance(list_type_or_node, Node):
        return get_const_val(list_type_or_node.type)
    elif isinstance(list_type_or_node, types.Const):
        return list_type_or_node.val
    else:
        raise errors.WeaveExpectedConstError("Expected a const value passed to `get`")


def op_get_return_type_from_inputs(inputs):
    return op_get_return_type(get_const_val(inputs["uri"]))


@op(
    name="getReturnType",
    input_type={"uri": types.String()},
    output_type=types.TypeType(),
)
def get_returntype(uri):
    return op_get_return_type(uri)


def _save(name, obj, setter_options, action=None):
    obj_uri = uris.WeaveURI.parse(name)
    branch = setter_options.get("branch")

    art_ref = obj_uri.to_ref()
    forked = None
    if isinstance(art_ref, artifact_fs.FilesystemArtifactRef):
        art = art_ref.artifact
        if branch is not None and branch != art.branch:
            forked = artifact_local.LocalArtifact(name=art.name, version=art.version)
            forked._original_uri = name

    ref = storage.save(
        obj,
        name=obj_uri.name + ":" + obj_uri.version,
        branch=branch,
        artifact=forked,
    )
    return ref.branch_uri


def _merge(name) -> str:
    """Save the object, propagating changes back to the original artifact"""
    obj_uri = uris.WeaveURI.parse(name)
    if not isinstance(
        obj_uri,
        (artifact_wandb.WeaveWBArtifactURI, artifact_local.WeaveLocalArtifactURI),
    ):
        raise errors.WeaveInternalError(
            "Cannot merge artifact of type %s" % type(obj_uri)
        )

    head_ref = obj_uri.to_ref()
    obj_metadata = head_ref.artifact.read_metadata()
    if "branch_point" not in obj_metadata:
        raise errors.WeaveInternalError(
            "Cannot merge into artifact without branch_point"
        )

    branch_point: artifact_fs.BranchPointType = obj_metadata["branch_point"]
    to_uri = uris.WeaveURI.parse(branch_point["original_uri"])
    if not isinstance(
        to_uri,
        (artifact_local.WeaveLocalArtifactURI, artifact_wandb.WeaveWBArtifactURI),
    ):
        raise errors.WeaveInternalError(
            "Cannot merge into artifact of type %s" % type(obj_uri)
        )

    to_ref = to_uri.to_ref()

    if isinstance(to_ref.artifact, artifact_wandb.WandbArtifact):
        original_artifact_hash = to_ref.artifact.commit_hash
    else:
        original_artifact_hash = to_ref.artifact.version

    if branch_point["commit"] != original_artifact_hash:
        raise errors.WeaveUnmergableArtifactsError(
            "Cannot merge artifacts: "
            "target artifact commit hash does not match branch point"
        )

    if isinstance(to_uri, artifact_wandb.WeaveWBArtifactURI):
        ref = storage._save_or_publish(
            head_ref.get(),
            name=to_uri.project_name + "/" + to_uri.name,
            publish=True,
        )
    else:
        if to_uri.version is None:
            raise errors.WeaveInternalError(
                "Cannot merge into artifact without version"
            )

        if len(to_uri.version) == 32 and is_hexadecimal(to_uri.version):
            name = to_uri.name
        else:
            name = to_uri.name + ":" + to_uri.version

        ref = storage._save_or_publish(
            head_ref.get(),
            name=name,
            branch=branch_point["branch"],
        )
    return ref.branch_uri


def _set(name, obj, setter_options, action=None):
    return _save(name, obj, setter_options, action=action)


@op(
    pure=False,
    setter=_set,
    name="get",
    input_type={"uri": types.String()},
    output_type=types.Any(),
    refine_output_type=get_returntype,
)
def get(uri):
    ref = ref_base.Ref.from_str(uri)
    if not ref.is_saved:
        return None
    return ref.get()


@op(
    pure=False,
    name="ref",
    render_info={"type": "function"},
    input_type={"uri": types.String()},
    # Only works on FilesystemArtifactRef right now, not generic.
    output_type=types.FilesystemArtifactRefType(),
)
def ref(uri):
    return ref_base.Ref.from_str(uri)


@op(
    pure=False,
    name="Ref-branch_point",
    input_type={"ref": types.FilesystemArtifactRefType()},
)
def ref_branch_point(ref) -> typing.Optional[artifact_fs.BranchPointType]:
    # TODO: execute automatically derefs. Need to not do that if input type is Ref!
    real_ref = storage._get_ref(ref)
    if not isinstance(real_ref, artifact_fs.FilesystemArtifactRef):
        raise errors.WeaveInternalError(
            "ref_branch_point only works on filesystem artifact refs"
        )
    return real_ref.branch_point


def execute_setter(node, value, action=None):
    if isinstance(node, graph.ConstNode):
        new_type = node.type
        if isinstance(new_type, types.Function):
            new_type = types.Function(new_type.input_types, value.type)
        return graph.ConstNode(new_type, value)
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
    # Reenable compile, in case we're already compiling. This happens when a Node
    # is stored in an object (as in the way that the Panel architecture passes
    # information down to the server). Compile doesn't walk into objects. So we need
    # to compile here when we are about to use them.
    with compile.enable_compile():
        return weave_internal.use(node)


def mutate_op_body(
    self,
    root_args: typing.Any,
    make_new_value: typing.Callable[[typing.Any], typing.Any],
):
    # This implements mutations. Note that its argument must be a
    # Node. You can call it like this:
    # weave.use(ops.set(weave_internal.const(csv[-1]["type"]), "YY"))

    self = compile.compile_fix_calls([self])[0]
    nodes = graph.linearize(self)
    if nodes is None:
        raise errors.WeaveInternalError("Set error")

    # Run through resolvers forward
    results = []
    op_inputs = []
    arg0 = list(nodes[0].from_op.inputs.values())[0].val
    for node in nodes:
        inputs = {}
        arg0_name = list(node.from_op.inputs.keys())[0]
        inputs[arg0_name] = arg0
        for name, input_node in list(node.from_op.inputs.items())[1:]:
            if not isinstance(input_node, graph.ConstNode):
                inputs[name] = storage.deref(weave_internal.use(input_node))
                # TODO: I was raising here, but the way I'm handling
                # default config in multi_distribution makes it necessary
                # to handle this case. This solution is more general,
                # but also more expensive. We should make use of the execution
                # cache (mutations should probably be planned by the compiler)
                # raise errors.WeaveInternalError("Set error")
            else:
                inputs[name] = input_node.val
        op_inputs.append(inputs)
        op_def = registry_mem.memory_registry.get_op(node.from_op.name)
        arg0 = op_def.resolve_fn(**inputs)
        results.append(arg0)

    # Make the updates backwards
    res = make_new_value(arg0)

    for i, (node, inputs, result) in reversed(
        list(enumerate(zip(nodes, op_inputs, results)))
    ):
        op_def = registry_mem.memory_registry.get_op(node.from_op.name)
        if not op_def.setter:
            return res
            # TODO: we can't raise the error here. Some of the tests
            # rely on partial setter chains.
            # raise errors.WeaveInternalError(
            #     "Set error. No setter declared for op: %s" % node.from_op.name
            # )
        args = list(inputs.values())
        args.append(res)
        if i == 0 and node.from_op.name == "get":
            # TODO hardcoded get to take root_args. Should just check if available on setter.
            args.append(root_args)
        try:
            res = op_def.setter.func(*args)  # type: ignore
        except AttributeError:
            res = op_def.setter(*args)

    return res


@mutation
def set(
    self: graph.Node[typing.Any], val: typing.Any, root_args: typing.Any = None
) -> typing.Any:
    if root_args is None:
        root_args = {}

    if isinstance(self, graph.ConstNode):
        return val

    return mutate_op_body(self, root_args, lambda _: val)


@mutation
def append(
    self: graph.Node[list], val: typing.Any, root_args: typing.Any = None
) -> typing.Any:
    if root_args is None:
        root_args = {}
    return mutate_op_body(self, root_args, lambda v: v + [val])


@mutation
def merge(self, root_args: typing.Any = None) -> typing.Any:
    self = compile.compile_fix_calls([self])[0]

    if not isinstance(self, graph.OutputNode):
        raise errors.WeaveInternalError("Merge target must be an OutputNode")

    if self.from_op.name != "get":
        raise errors.WeaveInternalError("Merge target must be a get")

    if not isinstance(self.from_op.inputs["uri"], graph.ConstNode):
        raise errors.WeaveInternalError("Merge op argument must be a const string")

    return _merge(self.from_op.inputs["uri"].val)


@mutation
def delete_artifact(
    self: graph.Node[typing.Any], root_args: typing.Any = None
) -> typing.Any:
    if not isinstance(self, graph.OutputNode):
        raise errors.WeaveInternalError("Merge target must be an OutputNode")

    if self.from_op.name != "get":
        raise errors.WeaveInternalError("Merge target must be a get")

    if not isinstance(self.from_op.inputs["uri"], graph.ConstNode):
        raise errors.WeaveInternalError("Merge op argument must be a const string")

    name = self.from_op.inputs["uri"].val

    obj_uri = uris.WeaveURI.parse(name)
    if not isinstance(
        obj_uri,
        (artifact_wandb.WeaveWBArtifactURI, artifact_local.WeaveLocalArtifactURI),
    ):
        raise errors.WeaveInternalError(
            "Cannot merge artifact of type %s" % type(obj_uri)
        )

    head_ref = obj_uri.to_ref()
    head_ref.artifact.delete()


@mutation
def rename_artifact(
    self: graph.Node[typing.Any], new_name: str, root_args: typing.Any = None
) -> typing.Any:
    if not isinstance(self, graph.OutputNode):
        raise errors.WeaveInternalError("Merge target must be an OutputNode")

    if self.from_op.name != "get":
        raise errors.WeaveInternalError("Merge target must be a get")

    if not isinstance(self.from_op.inputs["uri"], graph.ConstNode):
        raise errors.WeaveInternalError("Merge op argument must be a const string")

    name = self.from_op.inputs["uri"].val

    obj_uri = uris.WeaveURI.parse(name)
    if not isinstance(
        obj_uri,
        (artifact_wandb.WeaveWBArtifactURI, artifact_local.WeaveLocalArtifactURI),
    ):
        raise errors.WeaveInternalError(
            "Cannot merge artifact of type %s" % type(obj_uri)
        )

    head_ref = obj_uri.to_ref()
    head_ref.artifact.rename(new_name)


@weave_class(weave_type=types.Function)
class FunctionOps:
    @op(
        output_type=lambda input_type: input_type["self"].output_type,
    )
    def __call__(self, arg1: typing.Any):
        arg1_node = weave_internal.make_const_node(
            types.TypeRegistry.type_of(arg1), arg1
        )
        called = weave_internal.better_call_fn(self, arg1_node)  # type: ignore
        return weave_internal.use(called)


@weave_class(weave_type=types.RunType)
class Run:
    # TODO: the first arg type to these mutations should be Node[Run], not just
    # plain Run. They work for now but may not be callable from WeaveJS. We
    # should make weave_class automatically wrap the self arg in Node[] for
    # mutation ops!
    @mutation
    def set_state(self, state: str) -> None:
        r = typing.cast(runs.Run, self)
        set(r.state, state)

    @mutation
    def set_inputs(self, v: typing.Any) -> None:
        r = typing.cast(runs.Run, self)
        set(r.inputs, v)

    @mutation
    def set_output(self, v: typing.Any) -> None:
        r = typing.cast(runs.Run, self)
        set(r.output, v)

    @mutation
    def print(self, s: str) -> None:
        r = typing.cast(runs.Run, self)
        append(r.prints, s)

    @mutation
    def log(self, v: typing.Any) -> None:
        r = typing.cast(runs.Run, self)
        append(r.history, v)

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

            self = artifact_local.get_local_version(f"run-{self.id}", "latest")

        return self.output
