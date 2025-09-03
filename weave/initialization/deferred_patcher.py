"""
Deferred patching mechanism for PIL and MoviePy modules.

This module uses Python's import hook system to defer patching of PIL and MoviePy
until they are actually imported. This improves startup time and avoids importing
these heavy dependencies unless they're actually needed.
"""

import sys
from abc import ABC, abstractmethod
from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Optional, Sequence


class BaseDeferredPatcher(MetaPathFinder, ABC):
    """Base class for deferred patching of modules."""

    def __init__(self) -> None:
        self._patched = False

    @property
    @abstractmethod
    def module_names(self) -> list[str]:
        """Return the list of module names that trigger this patcher."""
        pass

    @abstractmethod
    def apply_patch(self) -> None:
        """Apply the patch to the module."""
        pass

    def should_patch(self, fullname: str) -> bool:
        """Check if this patcher should handle the given module."""
        return not self._patched and fullname in self.module_names

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]] = None,
        target: Optional[ModuleType] = None,
    ) -> Optional[ModuleSpec]:
        """Find spec for modules and return a spec with our custom loader if needed."""
        if not self.should_patch(fullname):
            return None

        # Let the default import machinery handle the actual import
        spec = None
        for finder in sys.meta_path:
            if finder is self:
                continue
            if hasattr(finder, "find_spec"):
                spec = finder.find_spec(fullname, path, target)
                if spec is not None:
                    break

        if spec is not None:
            # Wrap the loader to apply our patch after import
            spec.loader = PatchingLoader(spec.loader, self)
        return spec

    def check_already_imported(self) -> bool:
        """Check if any of the target modules are already imported."""
        return any(name in sys.modules for name in self.module_names)

    def install(self) -> None:
        """Install this patcher into sys.meta_path."""
        # If module is already imported, apply patch immediately
        if self.check_already_imported():
            self.apply_patch()
            self._patched = True
        
        # Still install the import hook (if not already installed) in case submodules are imported later
        if self not in sys.meta_path:
            # Insert at the beginning to ensure we catch imports before other finders
            sys.meta_path.insert(0, self)

    def uninstall(self) -> None:
        """Remove this patcher from sys.meta_path."""
        if self in sys.meta_path:
            sys.meta_path.remove(self)


class PatchingLoader(Loader):
    """Loader that applies patches after the module is loaded."""

    def __init__(self, wrapped_loader: Optional[Loader], patcher: BaseDeferredPatcher) -> None:
        self.wrapped_loader = wrapped_loader
        self.patcher = patcher

    def create_module(self, spec: ModuleSpec) -> Optional[ModuleType]:
        if self.wrapped_loader and hasattr(self.wrapped_loader, "create_module"):
            return self.wrapped_loader.create_module(spec)
        return None

    def exec_module(self, module: ModuleType) -> None:
        if self.wrapped_loader and hasattr(self.wrapped_loader, "exec_module"):
            self.wrapped_loader.exec_module(module)

        # Apply the patch after the module is loaded
        if not self.patcher._patched:
            self.patcher.apply_patch()
            self.patcher._patched = True


class PILDeferredPatcher(BaseDeferredPatcher):
    """Deferred patcher for PIL/Pillow library."""

    @property
    def module_names(self) -> list[str]:
        return ["PIL"]

    def apply_patch(self) -> None:
        """Apply thread-safety patch to PIL."""
        # Import lazily to avoid importing PIL at module load time
        from .pil_image_thread_safety import apply_threadsafe_patch_to_pil_image
        apply_threadsafe_patch_to_pil_image()


class MoviePyDeferredPatcher(BaseDeferredPatcher):
    """Deferred patcher for MoviePy library."""

    @property
    def module_names(self) -> list[str]:
        return ["moviepy"]

    def apply_patch(self) -> None:
        """Apply thread-safety patch to MoviePy."""
        # Import lazily to avoid importing moviepy at module load time
        from .moviepy_video_thread_safety import apply_threadsafe_patch_to_moviepy_video
        apply_threadsafe_patch_to_moviepy_video()


# Global patcher instances
_pil_patcher: Optional[PILDeferredPatcher] = None
_moviepy_patcher: Optional[MoviePyDeferredPatcher] = None


def install_deferred_patches() -> None:
    """Install the deferred patching mechanism for both PIL and MoviePy.
    
    This function checks if PIL or moviepy are already imported. If they are,
    it applies the patches immediately. Otherwise, it installs import hooks
    to apply patches when these modules are imported later.
    """
    global _pil_patcher, _moviepy_patcher

    # Install PIL patcher
    if _pil_patcher is None:
        _pil_patcher = PILDeferredPatcher()
        _pil_patcher.install()

    # Install MoviePy patcher
    if _moviepy_patcher is None:
        _moviepy_patcher = MoviePyDeferredPatcher()
        _moviepy_patcher.install()


def uninstall_deferred_patches() -> None:
    """Uninstall the deferred patching mechanism for both PIL and MoviePy."""
    global _pil_patcher, _moviepy_patcher

    if _pil_patcher is not None:
        _pil_patcher.uninstall()
        _pil_patcher = None

    if _moviepy_patcher is not None:
        _moviepy_patcher.uninstall()
        _moviepy_patcher = None


def install_pil_patch() -> None:
    """Install only the PIL deferred patching mechanism."""
    global _pil_patcher

    if _pil_patcher is None:
        _pil_patcher = PILDeferredPatcher()
        _pil_patcher.install()


def install_moviepy_patch() -> None:
    """Install only the MoviePy deferred patching mechanism."""
    global _moviepy_patcher

    if _moviepy_patcher is None:
        _moviepy_patcher = MoviePyDeferredPatcher()
        _moviepy_patcher.install()


def uninstall_pil_patch() -> None:
    """Uninstall only the PIL deferred patching mechanism."""
    global _pil_patcher

    if _pil_patcher is not None:
        _pil_patcher.uninstall()
        _pil_patcher = None


def uninstall_moviepy_patch() -> None:
    """Uninstall only the MoviePy deferred patching mechanism."""
    global _moviepy_patcher

    if _moviepy_patcher is not None:
        _moviepy_patcher.uninstall()
        _moviepy_patcher = None