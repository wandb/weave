"""Utilities for lazy loading of modules."""

import importlib
import sys
from typing import TYPE_CHECKING, Any


class LazyModule:
    """A lazy module wrapper that defers import until first access.
    
    This class allows deferring the import of heavy modules like NumPy
    until they are actually used, while maintaining type checking support.
    """
    
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None
    
    def _load(self) -> Any:
        """Load the module if not already loaded."""
        if self._module is None:
            self._module = importlib.import_module(self._module_name)
        return self._module
    
    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the loaded module."""
        module = self._load()
        return getattr(module, name)
    
    def __dir__(self):
        """Return the module's attributes for tab completion."""
        module = self._load()
        return dir(module)
    
    def __repr__(self):
        if self._module is None:
            return f"<LazyModule '{self._module_name}' (not loaded)>"
        return repr(self._module)


def lazy_import_numpy():
    """Get a lazy-loaded NumPy module that maintains type checking support.
    
    Usage:
        from weave.utils.lazy_import import lazy_import_numpy
        
        # For type checking, import the actual module
        if TYPE_CHECKING:
            import numpy as np
        else:
            np = lazy_import_numpy()
        
        # Now np can be used normally, but won't be imported until first access
        array = np.array([1, 2, 3])
    
    Returns:
        A LazyModule instance for NumPy that defers import until first use.
    """
    # Check if NumPy is already imported
    if 'numpy' in sys.modules:
        return sys.modules['numpy']
    
    return LazyModule('numpy')


def get_numpy():
    """Get NumPy module, importing it lazily if needed.
    
    This is an alternative pattern that can be used inline:
    
    Usage:
        from weave.utils.lazy_import import get_numpy
        
        def my_function(data):
            np = get_numpy()
            return np.array(data)
    
    Returns:
        The NumPy module.
    """
    # Check if already imported
    if 'numpy' in sys.modules:
        return sys.modules['numpy']
    
    # Import it fresh
    import numpy
    return numpy