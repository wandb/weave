"""Test that aliased weave imports are handled correctly in code capture."""

from collections.abc import Callable

import weave
import weave as weave_alias
import weave as wv
from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.trace.serialization.op_type import save_instance


def save_and_get_code(func: Callable) -> str:
    artifact = MemTraceFilesArtifact()
    save_instance(func, artifact, "obj")
    saved_code = artifact.path_contents["obj.py"]
    if isinstance(saved_code, bytes):
        saved_code = saved_code.decode()
    return saved_code


def test_standard_import():
    """Test that standard import weave works correctly."""

    @weave.op
    def standard_func():
        return "standard"

    code = save_and_get_code(standard_func)

    # Should only have one import weave
    import_lines = [
        l for l in code.splitlines() if l.strip().startswith("import weave")
    ]
    assert len(import_lines) == 1
    assert import_lines[0] == "import weave"

    # Should only have one decorator
    deco_lines = [l for l in code.splitlines() if "@" in l and "op" in l]
    assert len(deco_lines) == 1
    assert deco_lines[0] == "@weave.op()"


def test_aliased_import_wv():
    """Test that aliased import (wv) is handled correctly - should preserve the alias."""

    @wv.op
    def aliased_func():
        return "aliased"

    code = save_and_get_code(aliased_func)

    # Should have aliased import preserved
    import_lines = [
        l for l in code.splitlines() if l.strip().startswith("import weave")
    ]
    assert len(import_lines) == 1
    assert import_lines[0] == "import weave as wv"

    # Should only have one decorator using the alias
    decorator_lines = [l for l in code.splitlines() if "@" in l and "op" in l]
    assert len(decorator_lines) == 1
    assert decorator_lines[0] == "@wv.op()"


def test_aliased_import_custom_name():
    """Test that aliased import with custom name is handled correctly - should preserve the alias."""

    @weave_alias.op
    def custom_alias_func():
        return "custom"

    code = save_and_get_code(custom_alias_func)

    # Should have aliased import preserved
    import_lines = [
        l for l in code.splitlines() if l.strip().startswith("import weave")
    ]
    assert len(import_lines) == 1
    assert import_lines[0] == "import weave as weave_alias"

    # Should only have one decorator using the alias
    decorator_lines = [l for l in code.splitlines() if "@" in l and "op" in l]
    assert len(decorator_lines) == 1
    assert decorator_lines[0] == "@weave_alias.op()"


def test_op_with_parentheses():
    """Test that @wv.op() with parentheses is handled correctly - should preserve the alias."""

    @wv.op()
    def paren_func():
        return "parentheses"

    code = save_and_get_code(paren_func)

    # Should have aliased import preserved
    import_lines = [
        l for l in code.splitlines() if l.strip().startswith("import weave")
    ]
    assert len(import_lines) == 1
    assert import_lines[0] == "import weave as wv"

    # Should only have one decorator using the alias
    decorator_lines = [l for l in code.splitlines() if "@" in l and "op" in l]
    assert len(decorator_lines) == 1
    assert decorator_lines[0] == "@wv.op()"


def test_nested_function_with_alias():
    """Test that nested functions with aliased imports work correctly - should preserve the alias."""

    def outer():
        @wv.op
        def inner():
            return "nested"

        return inner

    inner_func = outer()
    code = save_and_get_code(inner_func)

    # Should have aliased import preserved
    import_lines = [
        l for l in code.splitlines() if l.strip().startswith("import weave")
    ]
    assert len(import_lines) == 1
    assert import_lines[0] == "import weave as wv"

    # Should have the decorator using the alias
    decorator_lines = [l for l in code.splitlines() if "@" in l and "op" in l]
    assert len(decorator_lines) == 1
    assert decorator_lines[0] == "@wv.op()"
