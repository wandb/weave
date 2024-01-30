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
from . import errors
from . import context_state
from . import weave_types as types
from . import registry_mem
from . import errors
from . import environment
from . import storage
from . import artifact_fs

from . import infer_types

if typing.TYPE_CHECKING:
    from .op_def import OpDef


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


class RefJSONEncoder(json.JSONEncoder):
    """Json encoder used for convert storage.to_json_with_refs result to python code"""

    SPECIAL_REF_TOKEN = "__WEAVE_REF__"

    def default(self, o):
        if isinstance(o, artifact_fs.FilesystemArtifactRef):
            if o.serialize_as_path_ref:
                ref_code = f"weave.storage.artifact_path_ref('{o.local_ref_str()}')"
            else:
                ref_code = f"weave.ref('{str(o)}')"

            # This will be a quoted json string in the json.dumps result. We put special
            # tokens in so we can remove the quotes in the final result
            return f"{self.SPECIAL_REF_TOKEN}{ref_code}.get(){self.SPECIAL_REF_TOKEN}"
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


class GetCodeDepsResult(typing.TypedDict):
    import_code: list[str]
    code: list[str]
    warnings: list[str]


def get_code_deps(
    fn: typing.Callable, artifact: artifact_fs.FilesystemArtifact
) -> GetCodeDepsResult:
    """Given a python function, return source code that contains the dependencies of that function.

    This will:
    - include any functions within the same module that are referenced within the function body
    - import any modules that are referenced within the function body or any referenced function bodies

    Current issues (to fix):
    - imported modules may be within the function's package, which doesn't work (any imported modules need
      to be present in the loading code)
    - doesn't serialize python requirements and other necessary system information
    - type annotations are not well handled, and may cause errors
    - refering to @weave.type() objects will cause errors

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
        return {"import_code": [], "code": [], "warnings": warnings}

    visitor = ExternalVariableFinder()
    visitor.visit(parsed)
    external_vars = list(visitor.external_vars)

    import_code = []
    code = []
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
            import_line = f"import {var_value.__name__}"
            if var_value.__name__ != var_name:
                import_line += f" as {var_name}"
            import_code.append(import_line)
        elif isinstance(var_value, py_types.FunctionType):
            if var_value.__module__ == fn.__module__:
                # For now, if the function is in another module.
                # we just import it. This is ok for libraries, but not
                # if the user has functions declared within their
                # package but outside of the op module.
                result = get_code_deps(var_value, artifact)
                fn_warnings = result["warnings"]
                fn_import_code = result["import_code"]
                fn_code = result["code"]

                import_code += fn_import_code

                code += fn_code
                code.append(inspect.getsource(var_value))

                warnings += fn_warnings
            else:
                if var_value.__module__.split(".")[0] == fn.__module__.split(".")[0]:
                    pass

                import_line = f"from {var_value.__module__} import {var_value.__name__}"
                if var_value.__name__ != var_name:
                    import_line += f"as {var_name}"

                import_code.append(import_line)

        else:
            if (
                hasattr(var_value, "__name__")
                and hasattr(var_value, "__module__")
                and var_value.__module__ != fn.__module__
            ):
                import_line = f"from {var_value.__module__} import {var_value.__name__}"
                if var_value.__name__ != var_name:
                    import_line += f"as {var_name}"
                import_code.append(import_line)
            else:
                try:
                    json_val = storage.to_json_with_refs(
                        var_value, artifact, path=[var_name]
                    )
                except (errors.WeaveTypeError, errors.WeaveSerializeError) as e:
                    warnings.append(
                        f"Serialization error for value of {var_name} needed by {fn}. Encountered:\n    {e}"
                    )
                else:
                    code_paragraph = (
                        f"{var_name} = "
                        + json.dumps(json_val, cls=RefJSONEncoder, indent=4)
                        + "\n"
                    )
                    code_paragraph = code_paragraph.replace(
                        f'"{RefJSONEncoder.SPECIAL_REF_TOKEN}', ""
                    )
                    code_paragraph = code_paragraph.replace(
                        f'{RefJSONEncoder.SPECIAL_REF_TOKEN}"', ""
                    )
                    code.append(code_paragraph)
    return {"import_code": import_code, "code": code, "warnings": warnings}


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


def find_last_weave_op_function(source_code: str):
    """Given a string of python source code, find the last function that is decorated with 'weave.op'."""
    tree = ast.parse(source_code)

    last_function = None

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, AsyncFunctionDef):
            for decorator in node.decorator_list:
                # Check if the decorator is 'weave.op'
                if isinstance(decorator, ast.Name) and decorator.id == "weave.op":
                    last_function = node
                    break  # Break the inner loop, continue with the next function
                # Check if the decorator is a call to 'weave.op()'
                elif (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "op"
                    and isinstance(decorator.func.value, ast.Name)
                    and decorator.func.value.id == "weave"
                ):
                    last_function = node
                    break  # Break the inner loop, continue with the next function

    return last_function


def dedupe_list(original_list: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for x in original_list:
        if x not in seen:
            deduped.append(x)
            seen.add(x)
    return deduped


class OpDefType(types.Type):
    def save_instance(self, obj: "OpDef", artifact, name):
        if obj.name.startswith("mapped_"):
            # Skip mapped (derived ops)
            return None
        if obj.is_builtin:
            with artifact.new_file(f"{name}.json") as f:
                json.dump({"name": obj.name}, f)
        else:
            # Type annotations are not well handled at the moment.
            # Get import statements for any annotations
            # code += (
            #     "\n".join(get_import_statements_for_annotations(obj.raw_resolve_fn))
            #     + "\n\n"
            # )

            result = get_code_deps(obj.raw_resolve_fn, artifact)
            import_code = result["import_code"]
            code = result["code"]
            warnings = result["warnings"]
            if warnings:
                message = f"Warning: Incomplete serialization for op {obj}. This op may not be reloadable"
                for warning in warnings:
                    message += "\n  " + warning
                if context_state.get_strict_op_saving():
                    raise errors.WeaveOpSerializeError(message)
                else:
                    # print(message)
                    pass

            # This is hacky handling of TypedDict annotations. Fixes
            # 2_images_gen notebook test.
            # Create TypedDict types for referenced TypedDicts
            resolve_annotations = obj.raw_resolve_fn.__annotations__
            for k, type_ in resolve_annotations.items():
                gen_type_code = generate_referenced_type_code(type_)
                if gen_type_code is not None:
                    code.append(gen_type_code)
                    if "typing" in gen_type_code:
                        import_code.insert(0, "import typing")

            code.append(textwrap.dedent(inspect.getsource(obj.raw_resolve_fn)))
            with artifact.new_file(f"{name}.py") as f:
                import_block = "\n".join(import_code)
                import_lines = ["import weave"] + import_block.split("\n")
                import_lines = dedupe_list(import_lines)
                import_lines = [l for l in import_lines if "weave.api" not in l]
                import_block = "\n".join(import_lines)
                code_block = "\n".join(code)
                f.write(f"{import_block}\n\n{code_block}")

    def load_instance(cls, artifact, name, extra=None):
        if environment.wandb_production():
            # Returning None here instead of erroring allows the Weaveflow app
            # to reference op defs without crashing.
            return None
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
            art_and_version_dir = module_path[: -(1 + len(file_name))]
            art_dir, version_subdir = art_and_version_dir.rsplit("/", 1)
            module_dir = art_dir
            import_name = (
                version_subdir
                + "."
                + ".".join(os.path.splitext(file_name)[0].split("/"))
            )

        sys.path.insert(0, os.path.abspath(module_dir))
        with context_state.no_op_register():
            try:
                mod = __import__(import_name, fromlist=[module_dir])
            except Exception as e:
                print("Op loading exception. This might be fine!", e)
                import traceback

                traceback.print_exc()
                return None
        sys.path.pop(0)

        # In the case where the saved op calls another op, we will have multiple
        # ops in the file. The file will look like
        # op1 = weave.ref('...').get()
        # @weave.op()
        # def op2():
        #     op1()
        #
        # We need to get the last declared op in the module. We can't do this
        # simply by iterating module attributes, because order is not guaranteed,
        # so we resort to looking at the source ast.
        last_op_function = find_last_weave_op_function(inspect.getsource(mod))
        if last_op_function is None:
            print(
                f"Unexpected Weave module saved in: {module_path}. No op defs found. All members: {dir(mod)}. {module_dir=} {import_name=}"
            )
            return None

        od: "OpDef" = getattr(mod, last_op_function.name)

        location = artifact.uri_obj.with_path(name)
        registry_mem.memory_registry.register_op(od, location=location)

        return od


def fully_qualified_opname(wrap_fn):
    op_module_file = os.path.abspath(inspect.getfile(wrap_fn))
    if op_module_file.endswith(".py"):
        op_module_file = op_module_file[:-3]
    elif op_module_file.endswith(".pyc"):
        op_module_file = op_module_file[:-4]
    return "file://" + op_module_file + "." + wrap_fn.__name__
