import textwrap
import json
import inspect
import os
import sys

from . import artifacts_local
from . import op_def
from . import errors
from . import context_state
from . import weave_types as types
from . import registry_mem


class OpDefType(types.Type):
    instance_class = op_def.OpDef
    instance_classes = op_def.OpDef

    def save_instance(self, obj: op_def.OpDef, artifact, name):

        if obj.is_builtin:
            with artifact.new_file(f"{name}.json") as f:
                json.dump({"name": obj.name}, f)
        else:
            code = "import weave\n" "\n"
            code += textwrap.dedent(inspect.getsource(obj.resolve_fn))
            with artifact.new_file(f"{name}.py") as f:
                f.write(code)

    def load_instance(cls, artifact, name, extra=None):
        try:
            with artifact.open(f"{name}.json") as f:
                op_spec = json.load(f)

            return registry_mem.memory_registry._ops[op_spec["name"]]
        except FileNotFoundError:
            pass

        path_with_ext = os.path.relpath(
            artifact.path(f"{name}.py"), start=artifacts_local.local_artifact_dir()
        )
        # remove the .py extension
        path = os.path.splitext(path_with_ext)[0]
        # convert filename into module path
        parts = path.split("/")
        module_path = ".".join(parts)

        sys.path.insert(0, artifacts_local.local_artifact_dir())
        with context_state.loading_op_location(artifact.location):
            # This has a side effect of registering the op
            mod = __import__(module_path)
        sys.path.pop(0)
        # We justed imported e.g. 'op-number-add.xaybjaa._obj'. Navigate from
        # mod down to _obj.
        for part in parts[1:]:
            mod = getattr(mod, part)

        op_defs = inspect.getmembers(mod, op_def.is_op_def)
        if len(op_defs) != 1:
            raise errors.WeaveInternalError(
                "Unexpected Weave module saved in: %s" % path
            )
        _, od = op_defs[0]
        return od


def fully_qualified_opname(wrap_fn):
    op_module_file = os.path.abspath(inspect.getfile(wrap_fn))
    if op_module_file.endswith(".py"):
        op_module_file = op_module_file[:-3]
    elif op_module_file.endswith(".pyc"):
        op_module_file = op_module_file[:-4]
    return "file://" + op_module_file + "." + wrap_fn.__name__
