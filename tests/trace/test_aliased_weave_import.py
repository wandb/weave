"""Test that aliased weave imports are handled correctly in code capture."""

import sys
import os
# Add the weave module to the path for standalone execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.trace.serialization.op_type import save_instance
import weave
import weave as wv
import weave as weave_alias


def test_standard_import():
    """Test that standard import weave works correctly."""
    
    @weave.op
    def standard_func():
        return "standard"
    
    artifact = MemTraceFilesArtifact()
    save_instance(standard_func, artifact, "obj")
    saved_code = artifact.path_contents["obj.py"]
    if isinstance(saved_code, bytes):
        saved_code = saved_code.decode()
    
    # Should only have one import weave
    import_lines = [line for line in saved_code.split('\n') if line.strip().startswith('import weave')]
    assert len(import_lines) == 1, f"Expected 1 import, got {len(import_lines)}: {import_lines}"
    assert import_lines[0].strip() == "import weave"
    
    # Should only have one decorator
    decorator_lines = [line for line in saved_code.split('\n') if '@' in line and 'op' in line]
    assert len(decorator_lines) == 1, f"Expected 1 decorator, got {len(decorator_lines)}: {decorator_lines}"
    assert "@weave.op()" in decorator_lines[0]


def test_aliased_import_wv():
    """Test that aliased import (wv) is handled correctly - should preserve the alias."""
    
    @wv.op
    def aliased_func():
        return "aliased"
    
    artifact = MemTraceFilesArtifact()
    save_instance(aliased_func, artifact, "obj")
    saved_code = artifact.path_contents["obj.py"]
    if isinstance(saved_code, bytes):
        saved_code = saved_code.decode()
    
    # Should have aliased import preserved
    import_lines = [line for line in saved_code.split('\n') if line.strip().startswith('import weave')]
    assert len(import_lines) == 1, f"Expected 1 import, got {len(import_lines)}: {import_lines}"
    assert import_lines[0].strip() == "import weave as wv"
    
    # Should only have one decorator using the alias
    decorator_lines = [line for line in saved_code.split('\n') if '@' in line and 'op' in line]
    assert len(decorator_lines) == 1, f"Expected 1 decorator, got {len(decorator_lines)}: {decorator_lines}"
    assert "@wv.op()" in decorator_lines[0]


def test_aliased_import_custom_name():
    """Test that aliased import with custom name is handled correctly - should preserve the alias."""
    
    @weave_alias.op
    def custom_alias_func():
        return "custom"
    
    artifact = MemTraceFilesArtifact()
    save_instance(custom_alias_func, artifact, "obj")
    saved_code = artifact.path_contents["obj.py"]
    if isinstance(saved_code, bytes):
        saved_code = saved_code.decode()
    
    # Should have aliased import preserved
    import_lines = [line for line in saved_code.split('\n') if line.strip().startswith('import weave')]
    assert len(import_lines) == 1, f"Expected 1 import, got {len(import_lines)}: {import_lines}"
    assert import_lines[0].strip() == "import weave as weave_alias"
    
    # Should only have one decorator using the alias
    decorator_lines = [line for line in saved_code.split('\n') if '@' in line and 'op' in line]
    assert len(decorator_lines) == 1, f"Expected 1 decorator, got {len(decorator_lines)}: {decorator_lines}"
    assert "@weave_alias.op()" in decorator_lines[0]


def test_op_with_parentheses():
    """Test that @wv.op() with parentheses is handled correctly - should preserve the alias."""
    
    @wv.op()
    def paren_func():
        return "parentheses"
    
    artifact = MemTraceFilesArtifact()
    save_instance(paren_func, artifact, "obj")
    saved_code = artifact.path_contents["obj.py"]
    if isinstance(saved_code, bytes):
        saved_code = saved_code.decode()
    
    # Should have aliased import preserved
    import_lines = [line for line in saved_code.split('\n') if line.strip().startswith('import weave')]
    assert len(import_lines) == 1, f"Expected 1 import, got {len(import_lines)}: {import_lines}"
    assert import_lines[0].strip() == "import weave as wv"
    
    # Should only have one decorator using the alias
    decorator_lines = [line for line in saved_code.split('\n') if '@' in line and 'op' in line]
    assert len(decorator_lines) == 1, f"Expected 1 decorator, got {len(decorator_lines)}: {decorator_lines}"
    assert "@wv.op()" in decorator_lines[0]


def test_nested_function_with_alias():
    """Test that nested functions with aliased imports work correctly - should preserve the alias."""
    
    def outer():
        @wv.op
        def inner():
            return "nested"
        return inner
    
    inner_func = outer()
    
    artifact = MemTraceFilesArtifact()
    save_instance(inner_func, artifact, "obj")
    saved_code = artifact.path_contents["obj.py"]
    if isinstance(saved_code, bytes):
        saved_code = saved_code.decode()
    
    # Should have aliased import preserved
    import_lines = [line for line in saved_code.split('\n') if line.strip().startswith('import weave')]
    assert len(import_lines) == 1, f"Expected 1 import, got {len(import_lines)}: {import_lines}"
    assert import_lines[0].strip() == "import weave as wv"
    
    # Should have the decorator using the alias
    assert "@wv.op()" in saved_code