import sys
import typing

import wandb

from . import op_def
from . import weave_types
from . import lazy
from . import errors


WANDB_ARTIFACT_SCHEME = "wandb-artifact://"
LOCAL_FILE_SCHEME = "file://"


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

    def _make_op_calls(self, op: op_def.OpDef, version: str):
        full_name = op.name + ":" + version
        op.lazy_call = lazy.make_lazy_call(
            op.resolve_fn, full_name, op.input_type, op.output_type
        )
        op.eager_call = lazy.make_eager_call(op.lazy_call)
        op.call_fn = lazy.make_call(op.eager_call, op.lazy_call)

    def register_op(self, op: op_def.OpDef):
        # Always save OpDefs any time they are declared
        from . import storage

        version = op_def.get_loading_op_version()
        is_loading = version is not None
        if version is None:
            # if we're not loading an existing op, save it.
            ref = storage.save(op, name=f"op-{op.name}")
            version = ref.version
        op.version = version

        self._make_op_calls(op, version)

        if not is_loading:
            self._ops[op.name] = op

        self._op_versions[(op.name, version)] = op
        return op

    def get_op(self, name: str) -> op_def.OpDef:
        if ":" in name:
            name, version = name.split(":", 1)
            return self._op_versions[(name, version)]
        if name in self._ops:
            return self._ops[name]
        raise errors.WeaveInternalError("Op not registered: %s" % name)

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

    def rename_op(self, name, new_name):
        """Internal use only, used during op bootstrapping at decorator time"""
        op = self._ops.pop(name)
        op.name = new_name
        self._ops[new_name] = op
        self._op_versions.pop((name, op.version))
        self._op_versions[(new_name, op.version)] = op
        self._make_op_calls(op, op.version)

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
