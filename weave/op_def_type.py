import collections
import textwrap
import json
import inspect
import types as py_types
import typing
import os
import sys
import ast

from . import artifact_local
from . import op_def
from . import errors
from . import context_state
from . import weave_types as types
from . import registry_mem
from . import errors

from . import infer_types


def type_code(type_):
    if isinstance(type_, py_types.GenericAlias) or isinstance(
        type_, typing._GenericAlias  # type: ignore
    ):
        args = ", ".join(type_code(t) for t in type_.__args__)
        if type_.__origin__ == list or type_.__origin__ == collections.abc.Sequence:
            return f"list[{args}]"
        elif type_.__origin__ == dict:
            return f"dict[{args}]"
        elif type_.__origin__ == typing.Union:
            return f"typing.Union[{args}]"
        else:
            return f"{type_.__origin__}[{args}]"
    else:
        return type_.__name__


def generate_referenced_type_code(type_):
    # Given a function that may have type annotations, generate non-redundant
    # code that declares any referenced types and their referenced types and
    # so on.

    # Absolutely horrible and hacky. This is not recursive in a tree/graph
    # way, its linear, so it'll only produce one TypedDict if there are many.
    # Using this to get the versioned object notebook working.
    if infer_types.is_typed_dict_like(type_):
        result = f"class {type_.__name__}(typing.TypedDict):\n"
        for k in type_.__annotations__:
            result += f"    {k}: {type_code(type_.__annotations__[k])}\n"
        return result
    elif isinstance(type_, py_types.GenericAlias) or isinstance(
        type_, typing._GenericAlias  # type: ignore
    ):
        return generate_referenced_type_code(type_.__args__[0])


def get_code_deps(fn, decl_locals):
    # Pretty horrible and hacky POC.
    # Tries to pull in other functions and modules referenced in the function
    # body. Generates a lot of repetition and not general. I just made it
    # work for specific cases that exist in the example notebooks currently.
    source = inspect.getsource(fn)
    try:
        parsed = ast.parse(source)
    except IndentationError:
        return ""
    import_code = ""
    for node in ast.walk(parsed):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            # A really bad way to check if a variable reference is for
            # a module!
            local_val = decl_locals.get(node.id)
            if isinstance(local_val, py_types.ModuleType):
                import_code += f"import {local_val.__name__} as {node.id}\n"
            elif isinstance(local_val, py_types.FunctionType):
                import_code += get_code_deps(local_val, decl_locals)
                import_code += inspect.getsource(local_val)
    return import_code


class OpDefType(types.Type):
    instance_class = op_def.OpDef
    instance_classes = op_def.OpDef

    def save_instance(self, obj: op_def.OpDef, artifact, name):
        if obj.is_builtin:
            with artifact.new_file(f"{name}.json") as f:
                json.dump({"name": obj.name}, f)
        else:
            code = "import typing\nimport weave\n"

            # Try to figure out module imports from the function body
            # (in a real hacky way as a POC)
            code += get_code_deps(obj.raw_resolve_fn, obj._decl_locals)

            # Create TypedDict types for referenced TypedDicts
            resolve_annotations = obj.raw_resolve_fn.__annotations__
            for k, type_ in resolve_annotations.items():
                gen_type_code = generate_referenced_type_code(type_)
                if gen_type_code is not None:
                    code += gen_type_code

            code += textwrap.dedent(inspect.getsource(obj.raw_resolve_fn))
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
            artifact.path(f"{name}.py"), start=artifact_local.local_artifact_dir()
        )
        # remove the .py extension
        path = os.path.splitext(path_with_ext)[0]
        # convert filename into module path
        parts = path.split("/")
        module_path = ".".join(parts)

        sys.path.insert(0, artifact_local.local_artifact_dir())
        with context_state.loading_op_location(artifact.uri_obj):
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
