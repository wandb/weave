from __future__ import annotations

import ast
import builtins
import inspect
import io
import json
import os
import re
import sys
import textwrap
import types as py_types
from _ast import AsyncFunctionDef, ExceptHandler
from typing import Any, Callable, TypedDict, get_args, get_origin

from weave.trace import settings
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.ipython import (
    ClassNotFoundError,
    get_class_source,
    is_running_interactively,
)
from weave.trace.op import Op, as_op, is_op
from weave.trace.refs import ObjectRef
from weave.trace.sanitize import REDACTED_VALUE, should_redact
from weave.trace.serialization import serializer
from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.trace_server.trace_server_interface_util import str_digest

WEAVE_OP_PATTERN = re.compile(r"@weave\.op(\(\))?")
WEAVE_OP_NO_PAREN_PATTERN = re.compile(r"@weave\.op(?!\()")

CODE_DEP_ERROR_SENTINEL = "<error>"


def arg_names(args: ast.arguments) -> set[str]:
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

    def __init__(self) -> None:
        self.external_vars: dict[str, bool] = {}
        self.scope_stack: list[set[str]] = [set()]  # Start with a global scope

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.scope_stack[-1].add(alias.asname or alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.scope_stack[-1].add(alias.asname or alias.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Add function name to the current scope
        self.scope_stack[-1].add(node.name)
        # Add function arguments to new scope
        self.scope_stack.append(arg_names(node.args))
        self.generic_visit(node)
        self.scope_stack.pop()  # Pop function scope when we exit the function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope_stack[-1].add(node.name)
        self.scope_stack.append(arg_names(node.args))
        self.generic_visit(node)
        self.scope_stack.pop()  # Pop function scope when we exit the function

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Add function arguments to the current scope
        self.scope_stack.append(arg_names(node.args))
        self.generic_visit(node)
        self.scope_stack.pop()  # Pop function scope when we exit the function

    def visit_ListComp(self, node: ast.ListComp) -> None:
        # Change visit order, visit generators first which is where variable
        # definitions happen
        for generator in node.generators:
            self.visit(generator)
        self.visit(node.elt)

    def visit_SetComp(self, node: ast.SetComp) -> Any:
        # Change visit order, visit generators first which is where variable
        # definitions happen
        for generator in node.generators:
            self.visit(generator)
        self.visit(node.elt)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        # Change visit order, visit generators first which is where variable
        # definitions happen
        for generator in node.generators:
            self.visit(generator)
        self.visit(node.elt)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        # Change visit order, visit generators first which is where variable
        # definitions happen
        for generator in node.generators:
            self.visit(generator)
        self.visit(node.key)
        self.visit(node.value)

    def visit_ExceptHandler(self, node: ExceptHandler) -> None:
        if node.name is None:
            return
        self.scope_stack[-1].add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        # print("  VISIT NAME", node.id, node.ctx)
        # If a variable is used (loaded) but not defined in any scope in the stack, and not builtin it's external
        # TODO: we don't capture python version, but builtins can change from version to version!
        if isinstance(node.ctx, ast.Store):
            self.scope_stack[-1].add(node.id)
        elif isinstance(node.ctx, ast.Load) and not any(
            node.id in scope for scope in self.scope_stack
        ):
            self.external_vars[node.id] = True


def resolve_var(fn: Callable, var_name: str) -> Any:
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

    def default(self, o: Any) -> Any:
        if isinstance(o, (ObjectRef)):
            ref_code = f"weave.ref('{str(o)}')"

        if ref_code is not None:
            # This will be a quoted json string in the json.dumps result. We put special
            # tokens in so we can remove the quotes in the final result
            return f"{self.SPECIAL_REF_TOKEN}{ref_code}.get(){self.SPECIAL_REF_TOKEN}"
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


class GetCodeDepsResult(TypedDict):
    import_code: list[str]
    code: list[str]
    warnings: list[str]


def get_source_notebook_safe(fn: Callable) -> str:
    # In ipython, we can't use inspect.getsource on classes defined in the notebook
    if is_running_interactively() and inspect.isclass(fn):
        try:
            src = get_class_source(fn)
        except ClassNotFoundError:
            # Not all times are we using notebook code - for example if a class
            # is defined int he Weave package itself.
            src = inspect.getsource(fn)
    else:
        src = inspect.getsource(fn)
    return textwrap.dedent(src)


def reconstruct_signature(fn: Callable) -> str:
    sig = inspect.signature(fn)
    module = sys.modules[fn.__module__]

    def make_annotation_str(annotation: Any) -> str:
        if isinstance(annotation, str):
            return annotation
        if annotation is inspect.Parameter.empty:
            return ""

        if (origin := get_origin(annotation)) is not None:
            args = get_args(annotation)
            replaced_args = [make_annotation_str(arg) for arg in args]
            replaced_args_str = ", ".join(replaced_args)

            if origin_name := getattr(origin, "__name__", None):
                return f"{origin_name}[{replaced_args_str}]"
            return f"{origin}[{replaced_args_str}]"

        if isinstance(annotation, type):
            # For builtins, just use the name
            if annotation.__module__ == "builtins":
                return annotation.__name__
            # Otherwise, check if the type is imported and use the alias if given
            for name, obj in module.__dict__.items():
                if isinstance(obj, py_types.ModuleType):
                    if annotation.__module__ == obj.__name__:
                        return f"{name}.{annotation.__name__}"
        return str(annotation)

    def quote_default_str(default: Any) -> Any:
        if isinstance(default, str):
            return f'"{default}"'
        return default

    params = []
    for name, param in sig.parameters.items():
        annotation_str = make_annotation_str(param.annotation)
        if param.default is param.empty:
            default = ""
        else:
            default = f" = {quote_default_str(param.default)}"
        params.append(f"{name}: {annotation_str}{default}")

    return_annotation = make_annotation_str(sig.return_annotation)

    sig_str = f"({', '.join(params)})"
    if return_annotation:
        sig_str += f" -> {return_annotation}"

    return sig_str


def get_source_or_fallback(fn: Callable, *, warnings: list[str]) -> str:
    if fn_is_op := is_op(fn):
        op = as_op(fn)
        fn = op.resolve_fn

    if not settings.should_capture_code() or (
        fn_is_op and not op._code_capture_enabled
    ):
        # This digest is kept for op versioning purposes
        digest = str_digest(inspect.getsource(fn))
        return textwrap.dedent(
            f"""
            def func(*args, **kwargs):
                ...  # Code-capture was disabled while saving this op (digest: {digest})
            """
        )

    try:
        return get_source_notebook_safe(fn)
    except OSError:
        pass

    try:
        sig_str = reconstruct_signature(fn)
    except Exception as e:
        warnings.append(f"Failed to reconstruct signature: {e}")
        sig_str = "(*args, **kwargs)"

    func_name = fn.__name__
    missing_code_template = textwrap.dedent(
        f"""
        def {func_name}{sig_str}:
            ... # Code-capture unavailable for this op
        """
    )[1:]  # skip first newline char

    return missing_code_template


def get_code_deps_safe(
    fn: Callable | type,  # A function or a class
    artifact: MemTraceFilesArtifact,
    depth: int = 0,
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
            code: str, the function body code.
            warnings: list[str], any warnings that occurred during the process.
    """
    try:
        return _get_code_deps(fn, artifact, {}, depth)
    except Exception as e:
        print(f"Error getting code deps for {fn}: {e}")
        return {
            "import_code": [],
            "code": [CODE_DEP_ERROR_SENTINEL],
            "warnings": [f"Error getting code dependencies for function {fn}: {e}"],
        }


def _get_code_deps(
    fn: Callable | type,  # A function or a class
    artifact: MemTraceFilesArtifact,
    seen: dict[Callable | type, bool],
    depth: int = 0,
) -> GetCodeDepsResult:
    warnings: list[str] = []
    if depth > 20:
        warnings = [
            "Recursion depth exceeded in get_code_deps, this may indicate circular dependencies, which are not yet handled."
        ]
        return {"import_code": [], "code": [], "warnings": warnings}

    source = get_source_or_fallback(fn, warnings=warnings)
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
        var_value = None
        if isinstance(fn, py_types.FunctionType):
            var_value = resolve_var(fn, var_name)

        try:
            # Some objects throw on equality comparison (like dataframes)
            equivalent = var_value == fn
        except ValueError:
            equivalent = False
        if equivalent:
            # If the variable is the function itself (recursion), we don't need to include it
            continue
        if var_value is None:
            # Try to resolve the variable from the module that the
            # item appears within.
            module = inspect.getmodule(fn)
            var_value = module.__dict__.get(var_name)
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
        elif isinstance(var_value, (py_types.FunctionType, type)) or is_op(var_value):
            if var_value.__module__ == fn.__module__:
                if not var_value in seen:
                    seen[var_value] = True
                    result = _get_code_deps(var_value, artifact, seen, depth + 1)
                    fn_warnings = result["warnings"]
                    fn_import_code = result["import_code"]
                    fn_code = result["code"]

                    import_code += fn_import_code

                    code += fn_code
                    code.append(get_source_notebook_safe(var_value))

                    warnings += fn_warnings
            else:
                # For now, if the function is in another module.
                # we just import it. This is ok for libraries, but not
                # if the user has functions declared within their
                # package but outside of the op module.
                if var_value.__module__.split(".")[0] == fn.__module__.split(".")[0]:
                    pass

                if is_op(var_value):
                    warnings.append(
                        f"Cross-module op dependencies are not yet serializable {var_value}"
                    )
                else:
                    import_line = (
                        f"from {var_value.__module__} import {var_value.__name__}"
                    )
                    if var_value.__name__ != var_name:
                        import_line += f"as {var_name}"

                    import_code.append(import_line)

        else:
            # Code saving for Ops using TypedDict and NotRequired was failing on Python 3.9
            # because NotRequired on 3.9 requires using typing_extensions and the implementation
            # doesn't have a __name__ attribute. We now check for _name as a fallback.
            # This came up in the context of persisting an inline custom object deserializer.
            var_value_name = getattr(
                var_value, "__name__", getattr(var_value, "_name", None)
            )
            if (
                var_value_name
                and hasattr(var_value, "__module__")
                and var_value.__module__ != fn.__module__
            ):
                import_line = f"from {var_value.__module__} import {var_value_name}"
                if var_value_name != var_name:
                    import_line += f" as {var_name}"
                import_code.append(import_line)
            else:
                try:
                    if (client := get_weave_client()) is None:
                        raise ValueError("Weave client not found")

                    from weave.trace.serialization.serialize import to_json

                    # Redact sensitive values
                    if should_redact(var_name):
                        json_val = REDACTED_VALUE
                    else:
                        json_val = to_json(var_value, client._project_id(), client)
                except Exception as e:
                    warnings.append(
                        f"Serialization error for value of {var_name} needed by {fn}. Encountered:\n    {e}"
                    )
                else:
                    if should_redact(var_name):
                        json_str = f'"{REDACTED_VALUE}"'
                    else:
                        json_str = json.dumps(json_val, cls=RefJSONEncoder, indent=4)
                    code_paragraph = f"{var_name} = " + json_str + "\n"
                    code_paragraph = code_paragraph.replace(
                        f'"{RefJSONEncoder.SPECIAL_REF_TOKEN}', ""
                    )
                    code_paragraph = code_paragraph.replace(
                        f'{RefJSONEncoder.SPECIAL_REF_TOKEN}"', ""
                    )
                    code.append(code_paragraph)
    return {"import_code": import_code, "code": code, "warnings": warnings}


def find_last_weave_op_function(
    source_code: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
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


def save_instance(obj: Op, artifact: MemTraceFilesArtifact, name: str) -> None:
    result = get_code_deps_safe(obj.resolve_fn, artifact)
    import_code = result["import_code"]
    code = result["code"]
    warnings = result["warnings"]
    if warnings:
        message = f"Warning: Incomplete serialization for op {obj}. This op may not be reloadable"
        for warning in warnings:
            message += "\n  " + warning

    op_function_code = get_source_or_fallback(obj, warnings=warnings)
    if not obj._code_capture_enabled:
        import_code = []
        code = []

    if settings.should_redact_pii():
        from weave.trace.pii_redaction import redact_pii_string

        op_function_code = redact_pii_string(op_function_code)

    if not WEAVE_OP_PATTERN.search(op_function_code):
        op_function_code = "@weave.op()\n" + op_function_code
    else:
        op_function_code = WEAVE_OP_NO_PAREN_PATTERN.sub(
            "@weave.op()", op_function_code
        )
    code.append(op_function_code)

    with artifact.new_file(f"{name}.py") as f:
        assert isinstance(f, io.StringIO)
        import_block = "\n".join(import_code)
        import_lines = ["import weave"] + import_block.split("\n")
        import_lines = dedupe_list(import_lines)
        import_lines = [l for l in import_lines if "weave.api" not in l]
        import_block = "\n".join(import_lines)
        code_block = "\n".join(code)
        f.write(f"{import_block}\n\n{code_block}")


def load_instance(
    artifact: MemTraceFilesArtifact,
    name: str,
) -> Op | None:
    file_name = f"{name}.py"
    module_path = artifact.path(file_name)

    # Python import caching means we can't just import "obj.py" here
    # because serialized ops would be cached at the "obj" key. We include
    # the version in the module name to avoid this. Since version names
    # are content hashes, this is correct.
    #
    art_and_version_dir = module_path[: -(1 + len(file_name))]
    art_dir, version_subdir = art_and_version_dir.rsplit("/", 1)
    module_dir = art_dir
    import_name = (
        version_subdir + "." + ".".join(os.path.splitext(file_name)[0].split("/"))
    )

    sys.path.insert(0, os.path.abspath(module_dir))
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

    od: Op = getattr(mod, last_op_function.name)
    return od


def fully_qualified_opname(wrap_fn: Callable) -> str:
    op_module_file = os.path.abspath(inspect.getfile(wrap_fn))
    if op_module_file.endswith(".py"):
        op_module_file = op_module_file[:-3]
    elif op_module_file.endswith(".pyc"):
        op_module_file = op_module_file[:-4]
    return "file://" + op_module_file + "." + wrap_fn.__name__


serializer.register_serializer(Op, save_instance, load_instance, is_op)
