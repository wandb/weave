import typing
import datetime

from weave.op_args import OpNamedArgs

from . import op_def
from . import op_def_type
from . import op_args
from . import weave_types
from . import errors
from . import context_state
from . import storage
from . import uris
from . import op_aliases


class Registry:
    _types: typing.Dict[str, weave_types.Type]

    # This most recent register_op() call for a given OpDef.name
    # TODO: Get rid of this! Always use versioning! This is a temporary
    # state.
    _ops: typing.Dict[str, op_def.OpDef]

    # common_name: name: op_def
    _ops_by_common_name: typing.Dict[str, dict[str, op_def.OpDef]]

    _op_versions: typing.Dict[typing.Tuple[str, str], op_def.OpDef]

    # Maintains a timestamp of when the registry was last updated.
    # This is useful for caching the ops dictionary when serving
    # the registry over HTTP.
    _updated_at: float

    def __init__(self):
        self._types = {}
        self._ops = {}
        self._ops_by_common_name = {}
        self._op_versions = {}
        self.mark_updated()

    def mark_updated(self) -> None:
        self._updated_at = datetime.datetime.now().timestamp()

    def updated_at(self) -> float:
        return self._updated_at

    def register_op(self, op: op_def.OpDef):
        self.mark_updated()
        # Always save OpDefs any time they are declared
        location = context_state.get_loading_op_location()
        is_loading = location is not None
        # do not save built-in ops today
        should_save = not is_loading and not op.is_builtin
        if should_save:
            # if we're not loading an existing op, save it.
            ref = storage.save(op, name=op.name + ":latest")
            version = ref.version
            location = ref.artifact.path_uri("obj")
        version = location.version if location is not None else None
        op.version = version
        op.location = location

        # if not is_loading:
        self._ops[op.name] = op
        self._ops_by_common_name.setdefault(op.common_name, {})[op.name] = op
        if version:
            self._op_versions[(op.name, version)] = op
        return op

    def have_op(self, op_name: str) -> bool:
        return op_name in self._ops

    def get_op(self, uri: str) -> op_def.OpDef:
        object_uri = uris.WeaveURI.parse(uri)
        if object_uri.version is not None:
            object_key = (object_uri.name, object_uri.version)
            if object_key in self._op_versions:
                res = self._op_versions[object_key]
            else:
                res = storage.get(uri)
                self._op_versions[object_key] = res
        elif object_uri.name in self._ops:
            res = self._ops[object_uri.name]
        else:
            if not ":" in uri:
                raise errors.WeaveMissingOpDefError("Op not registered: %s" % uri)
            res = storage.get(uri)
        if res is None:
            raise errors.WeaveMissingOpDefError("Op not registered: %s" % uri)
        return res

    def find_op_by_fn(self, lazy_local_fn):
        for op_def in self._op_versions.values():
            if op_def.call_fn == lazy_local_fn:
                return op_def
        raise Exception("Op def doesn't exist for %s" % lazy_local_fn)

    def find_ops_by_common_name(self, common_name: str) -> typing.List[op_def.OpDef]:
        aliases = op_aliases.get_op_aliases(common_name)
        ops: list[op_def.OpDef] = []
        for alias in aliases:
            ops.extend(self._ops_by_common_name.get(alias, {}).values())
        return ops

    def find_chainable_ops(
        self, arg0_type: weave_types.Type
    ) -> typing.List[op_def.OpDef]:
        def is_chainable(op):
            if not isinstance(op.input_type, op_args.OpNamedArgs):
                return False
            args = list(op.input_type.arg_types.values())
            if not args:
                return False
            return args[0].assign_type(arg0_type)

        return [op for op in self._ops.values() if is_chainable(op)]

    def load_saved_ops(self):
        for op_ref in storage.objects(op_def_type.OpDefType()):
            try:
                op_ref.get()
            except:
                # print("Failed to load non-builtin op: %s" % op_ref.uri)
                pass

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
        self.mark_updated()
        op = self._ops.pop(name)
        op.name = new_name
        self._ops[new_name] = op

        self._ops_by_common_name[op.common_name].pop(name)
        self._ops_by_common_name.setdefault(op.common_name, {})[new_name] = op

        old_version = op.version

        # TODO(DG): find a better way to do this than to save the op again
        # see comment here: https://github.com/wandb/weave-internal/pull/554#discussion_r1103875156
        if op.location is not None:
            ref = storage.save(op, name=new_name)
            location = ref.artifact.uri_obj
            version = ref.version
            op.version = version
            op.location = location

        if op.version is not None:
            self._op_versions.pop((name, old_version))
            self._op_versions[(new_name, op.version)] = op

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
