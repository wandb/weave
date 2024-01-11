from _ast import AsyncFunctionDef, ExceptHandler
import collections
import textwrap
import json
import inspect
import types as py_types
import typing
import os
import sys
import ast
import builtins
from typing import Any

from . import artifact_local
from . import op_def
from . import errors
from . import context_state
from . import weave_types as types
from . import registry_mem
from . import errors
from . import environment

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


def arg_names(args: ast.arguments):
    arg_names = set()
    for arg in args.args:
        arg_names.add(arg.arg)
    for arg in args.kwonlyargs:
        arg_names.add(arg.arg)
    for arg in args.posonlyargs:
        arg_names.add(arg.arg)
    if args.vararg:
        arg_names.add(args.vararg.arg)
    if args.kwarg:
        arg_names.add(args.kwarg.arg)
    return arg_names


class ExternalVariableFinder(ast.NodeVisitor):
    """Given a an AST of a python function, find all external variable references.

    External variable references are variables that are used in the function but
    not created in the function.

    The general strategy is to walk the AST keeping track of what variables are in
    scope. Any variables loads we encounter that are not in the current scope are
    external.
    """

    def __init__(self):
        self.external_vars = {}
        self.scope_stack = [set()]  # Start with a global scope

    def visit_Import(self, node):
        for alias in node.names:
            self.scope_stack[-1].add(alias.asname or alias.name)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.scope_stack[-1].add(alias.asname or alias.name)

    def visit_FunctionDef(self, node):
        # Add function name to the current scope
        self.scope_stack[-1].add(node.name)
        # Add function arguments to new scope
        self.scope_stack.append(arg_names(node.args))
        self.generic_visit(node)
        self.scope_stack.pop()  # Pop function scope when we exit the function

    def visit_AsyncFunctionDef(self, node) -> Any:
        self.scope_stack[-1].add(node.name)
        self.scope_stack.append(arg_names(node.args))
        self.generic_visit(node)
        self.scope_stack.pop()  # Pop function scope when we exit the function

    def visit_Lambda(self, node):
        # Add function arguments to the current scope
        self.scope_stack.append(arg_names(node.args))
        self.generic_visit(node)
        self.scope_stack.pop()  # Pop function scope when we exit the function

    def visit_ListComp(self, node) -> Any:
        # Change visit order, visit generators first which is where variable
        # definitions happen
        for generator in node.generators:
            self.visit(generator)
        self.visit(node.elt)

    def visit_SetComp(self, node) -> Any:
        # Change visit order, visit generators first which is where variable
        # definitions happen
        for generator in node.generators:
            self.visit(generator)
        self.visit(node.elt)

    def visit_GeneratorExp(self, node) -> Any:
        # Change visit order, visit generators first which is where variable
        # definitions happen
        for generator in node.generators:
            self.visit(generator)
        self.visit(node.elt)

    def visit_DictComp(self, node) -> Any:
        # Change visit order, visit generators first which is where variable
        # definitions happen
        for generator in node.generators:
            self.visit(generator)
        self.visit(node.key)
        self.visit(node.value)

    def visit_ExceptHandler(self, node: ExceptHandler) -> Any:
        self.scope_stack[-1].add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        # print("  VISIT NAME", node.id, node.ctx)
        # If a variable is used (loaded) but not defined in any scope in the stack, and not builtin it's external
        # TODO: we don't capture python version, but builtins can change from version to version!
        if isinstance(node.ctx, ast.Store):
            self.scope_stack[-1].add(node.id)
        elif isinstance(node.ctx, ast.Load) and not any(
            node.id in scope for scope in self.scope_stack
        ):
            self.external_vars[node.id] = True


def resolve_var(fn: typing.Callable, var_name: str):
    """Given a python function, resolve a non-local variable name."""
    # First to see if the variable is in the closure
    if fn.__closure__:
        closure_vars = {}
        # __code__.co_freevars is the closure variable names in order
        for vn, closure_cell in zip(fn.__code__.co_freevars, fn.__closure__):
            closure_vars[vn] = closure_cell.cell_contents
        if var_name in closure_vars:
            return closure_vars[var_name]
    if var_name in fn.__globals__:
        return fn.__globals__[var_name]
    return None


def get_code_deps(fn: typing.Callable) -> typing.Tuple[str, list[str]]:
    """Given a python function, return source code that contains the dependencies of that function.

    This will:
    - include any functions within the same module that are referenced within the function body
    - import any modules that are referenced within the function body or any referenced function bodies

    Current issues (to fix):
    - only handles json serializable constants in function closures. We need to use Weave serialization
      to save other values into the artifact and have a way of fetching them in the generated code
    - imported modules may be within the function's package, which doesn't work (any imported modules need
      to be present in the loading code)
    - doesn't serialize python requirements and other necessary system information

    Args:
        fn: The Python function to analyze.

    Returns:
        tupe: A tuple containing
            import_code: str, the code that should be included in the generated code to ensure all
                dependencies are available for the function body.
            warnings: list[str], any warnings that occurred during the process.
    """
    # Generates repeats.
    warnings: list[str] = []

    source = textwrap.dedent(inspect.getsource(fn))
    try:
        parsed = ast.parse(source)
    except SyntaxError:
        warnings.append(f"Could not parse source of function {fn}.")
        return "", warnings

    visitor = ExternalVariableFinder()
    visitor.visit(parsed)
    external_vars = list(visitor.external_vars)

    import_code = ""
    for var_name in external_vars:
        var_value = resolve_var(fn, var_name)
        # var_value = fn.__globals__.get(var_name)
        if var_value is None:
            if getattr(builtins, var_name, None):
                # Its a builtin, carry on
                continue
            warnings.append(
                f'Could not resolve var "{var_name}" declared in body of fn {fn}. This op will not be reloadable, but calls to it will be tracked'
            )
        elif isinstance(var_value, py_types.ModuleType):
            import_code += f"import {var_value.__name__} as {var_name}\n"
        elif isinstance(var_value, py_types.FunctionType):
            if var_value.__module__ == fn.__module__:
                # For now, if the function is in another module.
                # we just import it. This is ok for libraries, but not
                # if the user has functions declared within their
                # package but outside of the op module.
                fn_code_deps, fn_warnings = get_code_deps(var_value)
                warnings += fn_warnings
                import_code += fn_code_deps
                import_code += inspect.getsource(var_value)
            else:
                if var_value.__module__.split(".")[0] == fn.__module__.split(".")[0]:
                    pass
                import_code += (
                    f"from {var_value.__module__} import {var_value.__name__}"
                )
                if var_value.__name__ != var_name:
                    import_code += f"as {var_name}"
                import_code += "\n"

        else:
            if (
                hasattr(var_value, "__name__")
                and hasattr(var_value, "__module__")
                and var_value.__module__ != fn.__module__
            ):
                import_code += (
                    f"from {var_value.__module__} import {var_value.__name__}"
                )
                if var_value.__name__ != var_name:
                    import_code += f"as {var_name}"
                import_code += "\n"
            else:
                try:
                    import_code += f"{var_name} = " + json.dumps(var_value) + "\n"
                except TypeError:
                    # TODO: This should use weave artifact serialization for non-json serializable objects.
                    #     That way we can store numpy arrays, pytorch models, etc, that are captured by
                    #     function closures. We'll need a special weave.local_ref() to see to look an
                    #     object up from the current artifact context.
                    warnings.append(
                        f"Didn't serialize value of {var_name} needed by {fn}."
                    )
    return import_code, warnings


def get_import_statements_for_annotations(func) -> list[str]:
    """Ensures we have imports for all the types used in the function annotations."""
    annotations = func.__annotations__
    imports_needed = set()

    for annotation in annotations.values():
        if hasattr(annotation, "__module__") and hasattr(annotation, "__name__"):
            module_name = annotation.__module__
            class_name = annotation.__name__
            if module_name != "builtins":
                imports_needed.add(f"from {module_name} import {class_name}")

    return list(imports_needed)


class OpDefType(types.Type):
    instance_class = op_def.OpDef
    instance_classes = op_def.OpDef

    def save_instance(self, obj: op_def.OpDef, artifact, name):
        if obj.name.startswith("mapped_"):
            # Skip mapped (derived ops)
            return None
        if obj.is_builtin:
            with artifact.new_file(f"{name}.json") as f:
                json.dump({"name": obj.name}, f)
        else:
            code = "import typing\nimport weave\n"

            # Get import statements for any annotations
            code += (
                "\n".join(get_import_statements_for_annotations(obj.raw_resolve_fn))
                + "\n\n"
            )

            code_deps, warnings = get_code_deps(obj.raw_resolve_fn)
            if warnings:
                message = (
                    f"Did not fully serialize op {obj}. This op may not be reloadable, but calls to it will be versioned.\n"
                    + "\n  ".join(warnings)
                )
                if context_state.get_strict_op_saving():
                    raise errors.WeaveOpSerializeError(message)
                else:
                    print(message)

            code += code_deps

            # Note the above two stanzas are in the order they are to ensure
            # this case works.
            # from PIL import Image
            # def sin_image(f: int) -> Image.Image:
            #     pass
            # The first stanza will create "from PIL.Image import Image"
            # and the second will create "from PIL import Image". In this case
            # we want the latter.
            # This is a major hack to get a notebook working.

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
        if environment.wandb_production():
            # Returning None here instead of erroring allows the Weaveflow app
            # to reference op defs without crashing.
            return None
            # raise errors.WeaveInternalError(
            #     "Loading ops from artifacts is not supported in production mode."
            # )
        try:
            with artifact.open(f"{name}.json") as f:
                op_spec = json.load(f)

            return registry_mem.memory_registry._ops[op_spec["name"]]
        except FileNotFoundError:
            pass

        from . import artifact_wandb

        is_wandb_artifact = False
        if isinstance(artifact, artifact_wandb.WandbArtifact):
            is_wandb_artifact = True

        file_name = f"{name}.py"
        module_path = artifact.path(file_name)

        if is_wandb_artifact:
            module_dir = os.path.dirname(module_path)
            import_name = os.path.splitext(os.path.basename(module_path))[0]
        else:
            # Python import caching means we can't just import "obj.py" here
            # because serialized ops would be cached at the "obj" key. We include
            # the version in the module name to avoid this. Since version names
            # are content hashes, this is correct.
            #
            # module_path = {WEAVE_CACHE_DIR}/{USER}/local-artifacts/{ARTIFACT_NAME}/{ARTIFACT_VERSION}/{NAME_INCLUDING_SUB_PATHS}.py
            art_and_version_dir = module_path[: -(1 + len(file_name))]
            art_dir, version_subdir = art_and_version_dir.rsplit("/", 1)
            module_dir = art_dir
            import_name = (
                version_subdir
                + "."
                + ".".join(os.path.splitext(file_name)[0].split("/"))
            )

        # path_with_ext = os.path.relpath(
        #     artifact.path(f"{name}.py"), start=artifact_local.local_artifact_dir()
        # )
        # # remove the .py extension
        # path = os.path.splitext(path_with_ext)[0]
        # # convert filename into module path
        # parts = path.split("/")
        # module_path = ".".join(parts)

        sys.path.insert(0, os.path.abspath(module_dir))
        with context_state.loading_op_location(artifact.uri_obj.with_path(name)):
            # This has a side effect of registering the op
            # PR: Return None if we can't load the op?
            try:
                # Weaveflow Merge: fromlist correctly imports submodules
                mod = __import__(import_name, fromlist=[module_dir])
            except Exception as e:
                print("Op loading exception. This might be fine!", e)
                import traceback

                traceback.print_exc()
                return None
        sys.path.pop(0)
        # We justed imported e.g. 'op-number-add.xaybjaa._obj'. Navigate from
        # Weaveflow Merge: Commenting out, this does not look correct to me (tim), but
        # leaving it here in case I'm wrong.
        # if not is_wandb_artifact:
        #     try:
        #         mod = getattr(mod, "obj")
        #     except:
        #         raise errors.WeaveInternalError(f"{import_name=} {name=} {module_dir=}")

        # mod down to _obj.
        # for part in parts[1:]:
        #     mod = getattr(mod, part)

        op_defs = inspect.getmembers(mod, op_def.is_op_def)
        if len(op_defs) != 1:
            raise errors.WeaveInternalError(
                f"Unexpected Weave module saved in: {module_path}. Found {len(op_defs)} op defs, expected 1. All members: {dir(mod)}. {module_dir=} {import_name=} t={type(mod.call)}"
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
