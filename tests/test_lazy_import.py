"""Tests for lazy NumPy import functionality."""

import sys
from typing import TYPE_CHECKING

import pytest


def test_lazy_import_numpy_defers_import():
    """Test that lazy_import_numpy doesn't immediately import NumPy."""
    # Remove numpy from sys.modules if it's already imported
    if 'numpy' in sys.modules:
        del sys.modules['numpy']
    
    from weave.utils.lazy_import import lazy_import_numpy
    
    # Get the lazy module
    np = lazy_import_numpy()
    
    # NumPy should not be imported yet
    assert 'numpy' not in sys.modules
    
    # Access an attribute to trigger the import
    _ = np.array
    
    # Now NumPy should be imported
    assert 'numpy' in sys.modules


def test_lazy_import_numpy_functionality():
    """Test that lazy-imported NumPy works correctly."""
    from weave.utils.lazy_import import lazy_import_numpy
    
    np = lazy_import_numpy()
    
    # Test basic NumPy functionality
    arr = np.array([1, 2, 3])
    assert arr.shape == (3,)
    assert np.sum(arr) == 6
    assert np.mean(arr) == 2.0


def test_lazy_import_numpy_with_type_checking():
    """Test the TYPE_CHECKING pattern for type hints."""
    from typing import TYPE_CHECKING
    
    if TYPE_CHECKING:
        import numpy as np
    else:
        from weave.utils.lazy_import import lazy_import_numpy
        np = lazy_import_numpy()
    
    # This should work with type checkers and at runtime
    def process_array(data: list) -> 'np.ndarray':
        return np.array(data)
    
    result = process_array([1, 2, 3])
    assert result.shape == (3,)


def test_get_numpy_function():
    """Test the get_numpy helper function."""
    # Reset the global np variable
    import weave.utils.lazy_import as lazy_import_module
    lazy_import_module.np = None
    
    # Remove numpy from sys.modules if it's already imported
    if 'numpy' in sys.modules:
        del sys.modules['numpy']
    
    from weave.utils.lazy_import import get_numpy
    
    # NumPy should not be imported yet
    assert 'numpy' not in sys.modules
    
    # Call get_numpy to trigger import
    np = get_numpy()
    
    # Now NumPy should be imported
    assert 'numpy' in sys.modules
    assert np is not None
    
    # Test that subsequent calls return the same module
    np2 = get_numpy()
    assert np is np2


def test_lazy_module_dir():
    """Test that dir() works on lazy modules."""
    from weave.utils.lazy_import import lazy_import_numpy
    
    np = lazy_import_numpy()
    
    # dir() should work and include NumPy attributes
    attrs = dir(np)
    assert 'array' in attrs
    assert 'sum' in attrs
    assert 'mean' in attrs


def test_lazy_module_repr():
    """Test the repr of lazy modules."""
    # Remove numpy from sys.modules if it's already imported
    if 'numpy' in sys.modules:
        del sys.modules['numpy']
    
    from weave.utils.lazy_import import LazyModule
    
    lazy_np = LazyModule('numpy')
    
    # Before loading
    assert 'not loaded' in repr(lazy_np)
    
    # Trigger loading
    _ = lazy_np.array
    
    # After loading
    assert 'numpy' in repr(lazy_np)
    assert 'not loaded' not in repr(lazy_np)