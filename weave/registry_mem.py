import inspect
import os
import sys
import typing

import wandb

from . import errors
from . import forward_graph
from . import weave_types
from . import lazy


WANDB_ARTIFACT_SCHEME = "wandb-artifact://"
LOCAL_FILE_SCHEME = "file://"


class OpDef(object):
    name: str
    input_type: typing.Dict[str, weave_types.Type]
    output_type: typing.Union[
        weave_types.Type,
        typing.Callable[[typing.Dict[str, weave_types.Type]], weave_types.Type],
    ]
    setter = str

    def __init__(
        self,
        name,
        input_type,
        output_type,
        call_fn,
        resolve_fn,
        setter=None,
        render_info=None,
        pure=True,
    ):
        self.name = name
        self.input_type = input_type
        self.output_type = output_type
        self.call_fn = call_fn
        self.resolve_fn = resolve_fn
        self.setter = setter
        self.render_info = render_info
        self.pure = pure

    @property
    def simple_name(self):
        # We need this to get around the run job_type 64 char limit, and artifact name limitations.
        # TODO: This function will need to be stable! Let's make sure we like what we're doing here.
        if self.name.startswith("file://"):
            # Shorten because local file paths tend to blow out the 64 char job_type limit (we need
            # to fix that probably)
            return self.name.rsplit("/", 1)[1]
        elif self.name.startswith("wandb-artifact://"):
            return (
                self.name[len("wandb-artifact://") :]
                .replace(":", ".")
                .replace("/", "_")
            )
        else:
            # This is for builtins, which I think we may just want to get rid
            # of?
            return self.name

    @property
    def has_varargs(self):
        # TODO: Fix this, we need a way of propertly typing varargs functions!
        return list(self.input_type.keys())[0] == "manyX"

    def __str__(self):
        return "<OpDef: %s>" % self.name


class LookaheadOpDef(OpDef):
    def __str__(self):
        return "<LookaheadOpDef: %s>" % self.name

    def resolve(self, params, node: forward_graph.ForwardNode):
        return self.resolve_fn(params, node)


# TODO: this should be in execute or shared with the code there. (need to
# refactor it a bit to do this.)


def get_input_values(output_node):
    inputs = {}
    for param_name, param_node in output_node.from_op.inputs.items():
        try:
            inputs[param_name] = param_node.val
        except AttributeError:
            raise errors.WeaveInternalError("invalid node type: %s" % param_node)
    return inputs


def fully_qualified_opname(wrap_fn):
    op_module_file = os.path.abspath(inspect.getfile(wrap_fn))
    if op_module_file.endswith(".py"):
        op_module_file = op_module_file[:-3]
    elif op_module_file.endswith(".pyc"):
        op_module_file = op_module_file[:-4]
    return "file://" + op_module_file + "." + wrap_fn.__name__


def fetch_op(path):
    """Get an op from an artifact or local file.

    Args:
      path: <entity>/<project>/<artifact_name>:<version>/<module>.<op_name>
    """
    if path.startswith(WANDB_ARTIFACT_SCHEME):
        path = path[len(WANDB_ARTIFACT_SCHEME) :]
        entity, project, artifact, op_path = path.split("/")
        api = wandb.Api()
        artifact = api.artifact("%s/%s/%s" % (entity, project, artifact))
        path = artifact.download()
    elif path.startswith(LOCAL_FILE_SCHEME):
        path = path[len(LOCAL_FILE_SCHEME) :]
        path, op_path = path.rsplit("/", 1)
    else:
        raise Exception("Tried to fetch invalid op: " + path)

    # dynamic import
    sys.path.append(path)
    module_path, symbol_name = op_path.rsplit(".", 1)

    # Side of effect of importing a module containing ops is that we register the op
    #     (via the op decorator) using the local path to the op
    mod = __import__(module_path)
    sys.path.pop()

    lazy_local_call_fn = mod.__dict__[symbol_name]

    if not path.startswith(WANDB_ARTIFACT_SCHEME):
        return lazy_local_call_fn

    # if we're loading a globally registered op, replace the version that the decorator
    # registered above with a version that calls the global op
    found_op_def = memory_registry.find_op_by_fn(lazy_local_call_fn)
    lazy_call = lazy.make_lazy_call(
        found_op_def.resolve_fn, path, found_op_def.input_type, found_op_def.output_type
    )
    memory_registry.register_op(
        OpDef(
            path,
            found_op_def.input_type,
            found_op_def.output_type,
            lazy_call,
            found_op_def.resolve_fn,
        )
    )
    memory_registry.unregister_op(found_op_def.name)
    return lazy_call


class Registry(object):
    _types: typing.Dict[str, weave_types.Type]
    _ops: typing.Dict[str, OpDef]

    def __init__(self):
        self._types = {}
        self._ops = {}

    def register_op(self, op: OpDef):
        self._ops[op.name] = op

    def unregister_op(self, op_name):
        self._ops.pop(op_name)

    def get_op(self, name):
        # returns an OpDef
        if name in self._ops:
            return self._ops[name]
        fetch_op(name)  # This registers the op
        return self._ops[name]

    def find_op_by_fn(self, lazy_local_fn):
        for op_def in self._ops.values():
            if op_def.call_fn == lazy_local_fn:
                return op_def
        raise Exception("Op def doesn't exist for %s" % lazy_local_fn)

    def list_ops(self) -> typing.List[OpDef]:
        return list(self._ops.values())

    # def register_type(self, type: weave_types.Type):
    #    self._types[type.name] = type

    # def get_type(self, name):
    #    # TODO, don't repeat this all the time
    #    types = all_subclasses(weave_types.Type)
    #    for type in types:
    #        if type.name == name:
    #            return type
    #    raise Exception("type not found")


# Processes have a singleton MemoryRegistry
memory_registry = Registry()
