import sys
import typing

import wandb
from weave.uris import WeaveObjectURI

from . import op_def
from . import weave_types
from . import lazy
from . import errors


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


class Registry:
    _types: typing.Dict[str, weave_types.Type]

    # This most recent register_op() call for a given OpDef.name
    # TODO: Get rid of this! Always use versioning! This is a temporary
    # state.
    _ops: typing.Dict[str, op_def.OpDef]

    _op_versions: typing.Dict[tuple[str, str], op_def.OpDef]

    def __init__(self):
        self._types = {}
        self._ops = {}
        self._op_versions = {}

    def register_op(self, op: op_def.OpDef):
        # Always save OpDefs any time they are declared
        from . import storage

        version = op_def.get_loading_op_version()
        is_loading = version is not None
        object_uri = WeaveObjectURI.parsestr(op.name)
        object_key = object_uri.uri()
        op_id = op.name
        if not is_loading and object_uri.scheme:
            # if we're not loading an existing op, save it.
            ref = storage.save(op, name=op_id)
            version = ref.version
            op_id = ref.artifact.uri()
            print("op_id", op_id)
        op.version = version

        op_full_id = op_id + ":" + version
        op.call_fn = lazy.make_lazy_call(
            op.resolve_fn, op_full_id, op.input_type, op.output_type
        )
        op.call_fn.op_def = op
        op.call_fn.is_weave = True

        if not is_loading:
            self._ops[op_id] = op

        self._op_versions[(op_id, version)] = op
        return op

    def get_op(self, uri: str) -> op_def.OpDef:
        from . import storage

        object_uri = WeaveObjectURI.parsestr(uri)
        object_key = object_uri.uri()
        if object_uri.version is not None:
            if object_key in self._op_versions:
                res = self._op_versions[object_key]
            else:
                res = storage.get(uri)
                self._op_versions[object_key] = res
        elif uri in self._ops:
            res = self._ops[uri]
        else:
            res = storage.get(object_key)
        if res is None:
            raise errors.WeaveInternalError("Op not registered: %s" % uri)
        return res

    def find_op_by_fn(self, lazy_local_fn):
        for op_def in self._op_versions.values():
            if op_def.call_fn == lazy_local_fn:
                return op_def
        raise Exception("Op def doesn't exist for %s" % lazy_local_fn)

    def list_ops(self) -> typing.List[op_def.OpDef]:
        # Note this uses self._ops, so provides the most recent registered op, which could
        # be the last one we loaded() [rather than the last one the user declared] which
        # is incorrect behavior
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
