"""Deferred patching system for PIL thread safety."""

import importlib.abc
import importlib.machinery
import sys
from typing import Optional, Sequence, Union

_pil_patch_installed = False


class _PILPatchingMetaFinder(importlib.abc.MetaPathFinder):
    """Meta path finder that applies thread-safety patch when PIL is imported."""

    def __init__(self) -> None:
        self.patched = False
        # Check if PIL is already imported
        if "PIL" in sys.modules or "PIL.ImageFile" in sys.modules:
            self._apply_patch()

    def _apply_patch(self) -> None:
        """Apply the thread-safety patch to PIL if not already applied."""
        if not self.patched:
            self.patched = True
            from weave.initialization.pil_image_thread_safety import (
                apply_threadsafe_patch_to_pil_image,
            )
            apply_threadsafe_patch_to_pil_image()

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[Union[bytes, str]]] = None,
        target: Optional[object] = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        """Apply patch when PIL modules are imported."""
        if not self.patched and fullname in ("PIL", "PIL.ImageFile"):
            self._apply_patch()
        return None


def ensure_pil_patch_installed() -> None:
    """Install the PIL patching import hook if not already installed.
    
    This function sets up an import hook that will automatically apply
    thread-safety patches when PIL is imported. If PIL is already imported
    when this is called, the patch is applied immediately.
    
    This is idempotent - calling it multiple times has no additional effect.
    """
    global _pil_patch_installed
    if not _pil_patch_installed:
        finder = _PILPatchingMetaFinder()
        sys.meta_path.insert(0, finder)
        _pil_patch_installed = True