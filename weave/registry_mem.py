import sys
import typing

import wandb

from . import op_def
from . import weave_types
from . import lazy


WANDB_ARTIFACT_SCHEME = "wandb-artifact://"
LOCAL_FILE_SCHEME = "file://"


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
        op_def.OpDef(
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
    _ops: typing.Dict[str, op_def.OpDef]

    def __init__(self):
        self._types = {}
        self._ops = {}

    def register_op(self, op: op_def.OpDef):
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

    def list_ops(self) -> typing.List[op_def.OpDef]:
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
