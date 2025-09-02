"""Test that aliased weave imports are handled correctly in code capture."""

from collections.abc import Callable

import weave
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


STANDARD_FUNC_CODE = """import weave

@weave.op()
def standard_func(): ...
"""


def test_standard_import():
    """Test that standard import weave works correctly."""

    @weave.op
    def standard_func(): ...

    code = save_and_get_code(standard_func)
    assert code == STANDARD_FUNC_CODE


ALIASED_FUNC_CODE = """import weave as wv

@wv.op()
def aliased_func(): ...
"""


def test_aliased_import_wv():
    """Test that aliased import (wv) is handled correctly - should preserve the alias."""

    @wv.op
    def aliased_func(): ...

    code = save_and_get_code(aliased_func)
    assert code == ALIASED_FUNC_CODE


ALIASED_FUNC_CODE_WITH_PARENTHESES = """import weave as wv

@wv.op()
def aliased_func(): ...
"""


def test_op_with_parentheses():
    """Test that @wv.op() with parentheses is handled correctly - should preserve the alias."""

    @wv.op()
    def paren_func(): ...

    code = save_and_get_code(paren_func)
    assert code == ALIASED_FUNC_CODE_WITH_PARENTHESES


NESTED_FUNC_CODE = """import weave as wv

def outer():
    @wv.op()
    def inner(): ...

    return inner
"""
