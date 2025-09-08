import importlib
from functools import cached_property
from types import ModuleType
from typing import Any


class LazyModule:
    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, item: str) -> Any:
        if not self._is_available:
            raise ImportError(f"Module {self._name} is not available")
        return getattr(self._module, item)

    @cached_property
    def _module(self) -> ModuleType:
        return importlib.import_module(self._name)

    @cached_property
    def _is_available(self) -> bool:
        try:
            importlib.import_module(self._name)
        except ImportError:
            return False
        return True
