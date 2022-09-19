import typing

from weave.op_args import OpNamedArgs
import functools

from . import op_def
from . import weave_types
from . import lazy
from . import errors
from . import context_state
from . import storage
from . import uris


class Registry:
    _types: typing.Dict[str, weave_types.Type]

    # This most recent register_op() call for a given OpDef.name
    # TODO: Get rid of this! Always use versioning! This is a temporary
    # state.
    _ops: typing.Dict[str, op_def.OpDef]

    _op_versions: typing.Dict[typing.Tuple[str, str], op_def.OpDef]

    def __init__(self):
        self._types = {}
        self._ops = {}
        self._op_versions = {}

    def _make_op_calls(
        self, op: op_def.OpDef, uri: typing.Optional[uris.WeaveURI] = None
    ):
        op_uri = uri.uri if uri is not None else op.uri
        op.lazy_call = lazy.make_lazy_call(
            op.resolve_fn, op_uri, op.input_type, op.output_type, op.refine_output_type
        )
        op.eager_call = lazy.make_eager_call(op.lazy_call, op)
        op.call_fn = lazy.make_call(op.eager_call, op.lazy_call)

    def register_op(self, op: op_def.OpDef):
        # Always save OpDefs any time they are declared

        location = context_state.get_loading_op_location()
        is_loading = location is not None
        # do not save built-in ops today
        should_save = not is_loading and not op.is_builtin
        if should_save:
            # if we're not loading an existing op, save it.
            ref = storage.save(op, name=op.name)
            version = ref.version
            location = ref.artifact.location
        version = location.version if location is not None else None
        op.version = version

        self._make_op_calls(op, location)
        if not is_loading:
            self._ops[op.name] = op
        if version:
            self._op_versions[(op.name, version)] = op
        return op

    # This is hotspot in execute_fast because we call it a lot
    # TODO: fix in execute_fast
    @functools.cache
    def get_op(self, uri: str) -> op_def.OpDef:
        object_uri = uris.WeaveURI.parse(uri)
        if object_uri.version is not None:
            object_key = (object_uri.full_name, object_uri.version)
            if object_key in self._op_versions:
                res = self._op_versions[object_key]
            else:
                res = storage.get(uri)
                self._op_versions[object_key] = res
        elif object_uri.full_name in self._ops:
            res = self._ops[object_uri.full_name]
        else:
            res = storage.get(uri)
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

    # Currently this just returns all ops that take no arguments.
    # Perhaps a better extension is to require a return type that
    # subclasses some abstract package type?
    def list_packages(self) -> typing.List[op_def.OpDef]:
        packages = [
            a
            for a in list(self._ops.values())
            if isinstance(a.input_type, OpNamedArgs)
            and len(a.input_type.arg_types.keys()) == 0
        ]
        return packages

    def rename_op(self, name, new_name):
        """Internal use only, used during op bootstrapping at decorator time"""
        op = self._ops.pop(name)
        op.name = new_name
        self._ops[new_name] = op
        if op.version is not None:
            self._op_versions.pop((name, op.version))
            self._op_versions[(new_name, op.version)] = op
        self._make_op_calls(op)

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
