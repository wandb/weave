"""Lazy import utilities that preserve type hints and autocomplete."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING, Any, Optional

class LazyModule:
    """A lazy module proxy that imports the actual module on first attribute access.
    
    This preserves type hints and autocomplete by using TYPE_CHECKING imports.
    Supports submodule access and attribute extraction.
    """
    
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module: Optional[Any] = None
        self._submodules: dict[str, LazyModule] = {}
    
    def _load(self) -> Any:
        """Load the module if not already loaded."""
        if self._module is None:
            self._module = importlib.import_module(self._module_name)
        return self._module
    
    def __getattr__(self, name: str) -> Any:
        """Lazy load the module and get the attribute.
        
        This handles both regular attributes and submodules.
        """
        # Check if this might be a submodule
        submodule_name = f"{self._module_name}.{name}"
        
        # Try to get it as an attribute first
        try:
            module = self._load()
            attr = getattr(module, name)
            
            # If it's a module, wrap it in a LazyModule for continued lazy behavior
            if isinstance(attr, type(sys)):  # Check if it's a module type
                if name not in self._submodules:
                    self._submodules[name] = LazyModule(submodule_name)
                return self._submodules[name]
            
            return attr
        except AttributeError:
            # Maybe it's a submodule that needs to be imported
            try:
                if name not in self._submodules:
                    # Try to import as a submodule
                    self._submodules[name] = LazyModule(submodule_name)
                return self._submodules[name]
            except ImportError:
                raise AttributeError(f"module '{self._module_name}' has no attribute '{name}'")
    
    def __dir__(self) -> list[str]:
        """Return the module's attributes for autocomplete."""
        module = self._load()
        return dir(module)
    
    def __repr__(self) -> str:
        if self._module is None:
            return f"<LazyModule '{self._module_name}' (not loaded)>"
        return f"<LazyModule '{self._module_name}' (loaded)>"


def lazy_import(module_name: str) -> LazyModule:
    """Create a lazy import for a module.
    
    Usage:
        # At module level:
        from typing import TYPE_CHECKING
        
        if TYPE_CHECKING:
            import numpy as np  # This provides type hints
        else:
            from weave.trace.lazy_import import lazy_import
            np = lazy_import("numpy")  # This provides runtime lazy loading
    
    This pattern allows:
    - Type checkers to see the real module for type hints
    - Runtime to use lazy loading
    - IDEs to provide proper autocomplete
    
    Args:
        module_name: The name of the module to import lazily
        
    Returns:
        A LazyModule proxy that will import the real module on first use
    """
    return LazyModule(module_name)


def lazy_from_import(module_name: str, *names: str) -> tuple[Any, ...] | Any:
    """Create lazy imports for specific attributes from a module.
    
    Usage:
        # For single import:
        if TYPE_CHECKING:
            from numpy import array
        else:
            array = lazy_from_import("numpy", "array")
        
        # For multiple imports:
        if TYPE_CHECKING:
            from numpy import array, ndarray, asarray
        else:
            array, ndarray, asarray = lazy_from_import("numpy", "array", "ndarray", "asarray")
    
    Args:
        module_name: The name of the module to import from
        *names: The attribute names to import
        
    Returns:
        A single LazyAttribute if one name, or tuple of LazyAttributes if multiple
    """
    class LazyFromImport:
        """Proxy for a specific attribute from a module."""
        def __init__(self, module_name: str, attr_name: str):
            self.module_name = module_name
            self.attr_name = attr_name
            self._value = None
            self._loaded = False
        
        def _load(self):
            if not self._loaded:
                module = importlib.import_module(self.module_name)
                self._value = getattr(module, self.attr_name)
                self._loaded = True
            return self._value
        
        def __call__(self, *args, **kwargs):
            """If the imported item is callable, call it."""
            return self._load()(*args, **kwargs)
        
        def __getattr__(self, name):
            """Get attributes from the lazy-loaded value."""
            return getattr(self._load(), name)
        
        def __getitem__(self, key):
            """Support indexing if the imported item supports it."""
            return self._load()[key]
        
        def __repr__(self):
            if self._loaded:
                return repr(self._value)
            return f"<LazyFromImport '{self.attr_name}' from '{self.module_name}' (not loaded)>"
    
    imports = [LazyFromImport(module_name, name) for name in names]
    
    if len(imports) == 1:
        return imports[0]
    return tuple(imports)


class LazyAttribute:
    """A lazy attribute that imports and caches on first access.
    
    This is useful for module-level attributes that depend on optional imports.
    """
    
    def __init__(self, loader_func):
        self.loader_func = loader_func
        self.value = None
        self.loaded = False
        self.load_error = None
    
    def get(self):
        """Get the attribute value, loading if necessary."""
        if not self.loaded:
            try:
                self.value = self.loader_func()
                self.loaded = True
            except ImportError as e:
                self.load_error = e
                self.loaded = True
        
        if self.load_error:
            raise self.load_error
        
        return self.value