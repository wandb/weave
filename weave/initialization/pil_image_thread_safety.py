"""
This file exposes functions to make the PIL ImageFile thread-safe and revert those changes:
- `apply_threadsafe_patch_to_pil_image`
- `undo_threadsafe_patch_to_pil_image`
- `register_pil_import_hook` - Deferred patching using importlib MetaPathFinder

There is a discussion here: https://github.com/python-pillow/Pillow/issues/4848#issuecomment-671339193 in which
the author claims that the Pillow library is thread-safe. However, empirical evidence suggests otherwise.

Specifically, the `ImageFile.load` method is not thread-safe because it:
1. Closes and deletes an open file handler
2. Modifies properties of the ImageFile object (namely the `im` property which contains the underlying image data)

Inside Weave, we use threads to parallelize work which may involve Images. This thread-safety issue has manifested
not only in our persistence layer but also in user code where loaded images are accessed across threads.

We use a MetaPathFinder to defer patching until PIL is actually imported, improving startup performance.
"""

import importlib.abc
import importlib.machinery
import logging
import sys
import threading
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Global state
# `_patched` is a boolean that indicates whether the thread-safety patch has been applied
# `_original_methods` is a dictionary that stores the original methods of the ImageFile class
# `_new_lock_lock` is a lock that is used to create a new lock for each ImageFile instance
# `_fallback_load_lock` is a global lock that is used to ensure thread-safe image loading when per-instance locking fails
_patched = False
_original_methods: dict[str, Optional[Callable]] = {"load": None}
_new_lock_lock = threading.RLock()
_fallback_load_lock = threading.RLock()


def apply_threadsafe_patch_to_pil_image() -> None:
    """Apply thread-safety patch to PIL ImageFile class.

    This function is idempotent - calling it multiple times has no additional effect.
    If PIL is not installed or if patching fails, the function will handle the error gracefully.
    
    Note: This function assumes PIL is already imported and will import PIL.ImageFile
    to apply the patches.
    """
    global _patched

    if _patched:
        return

    try:
        _apply_threadsafe_patch()
    except ImportError:
        pass
    except Exception as e:
        logger.info(f"Failed to patch PIL.ImageFile.ImageFile: Unexpected error - {e}")
    else:
        _patched = True


def _apply_threadsafe_patch() -> None:
    """Internal function that performs the actual thread-safety patching of PIL ImageFile.

    This imports PIL.ImageFile and applies the patch. Should only be called when
    PIL is already imported.

    Raises:
        ImportError: If PIL is not installed
        Exception: For any other unexpected errors during patching
    """
    # Only import when we're actually applying the patch
    # This ensures we don't eagerly load PIL
    from PIL.ImageFile import ImageFile

    global _original_methods

    # Store original methods
    _original_methods["load"] = ImageFile.load
    old_load = ImageFile.load

    @wraps(old_load)
    def new_load(self: ImageFile, *args: Any, **kwargs: Any) -> Any:
        # This function wraps PIL's ImageFile.load method to make it thread-safe
        # by ensuring only one thread can load an image at a time per ImageFile instance.

        # We use a per-instance lock to allow concurrent loading of different images
        # while preventing concurrent access to the same image.
        try:
            # Create a new lock for this ImageFile instance if it doesn't exist.
            # The lock creation itself needs to be thread-safe, hence _new_lock_lock.
            # Note: this `_new_lock_lock` is global as opposed to per-instance, else
            # it would be possible for the same ImageFile to be loaded by multiple threads
            # thereby creating a race where different threads would be each minting their
            # own lock for the same ImageFile!
            if not hasattr(self, "_weave_load_lock"):
                with _new_lock_lock:
                    # Double-check pattern: verify the attribute still doesn't exist
                    # after acquiring the lock to prevent race conditions
                    if not hasattr(self, "_weave_load_lock"):
                        setattr(self, "_weave_load_lock", threading.RLock())
            lock = getattr(self, "_weave_load_lock")  # noqa: B009

        except Exception:
            # If anything goes wrong with the locking mechanism,
            # fall back to the global lock for safety
            lock = _fallback_load_lock
        # Acquire the instance-specific lock before loading the image.
        # This ensures thread-safety by preventing concurrent:
        # - Modification of the 'im' property
        # - Access to the file handler
        with lock:
            return old_load(self, *args, **kwargs)

    # Replace the load method with our thread-safe version
    ImageFile.load = new_load  # type: ignore


def undo_threadsafe_patch_to_pil_image() -> None:
    """Revert the thread-safety patch applied to PIL ImageFile class.

    This function is idempotent - if the patch hasn't been applied, this function does nothing.
    If the patch has been applied but can't be reverted, an error message is printed.
    """
    global _patched

    if not _patched:
        return

    try:
        _undo_threadsafe_patch()
    except ImportError:
        pass
    except Exception as e:
        logger.info(
            f"Failed to unpatch PIL.ImageFile.ImageFile: Unable to restore original methods - {e}"
        )
    else:
        _patched = False


def _undo_threadsafe_patch() -> None:
    """Internal function that performs the actual removal of thread-safety patches.

    Raises:
        ImportError: If PIL is not installed
        Exception: For any other unexpected errors during unpatching
    """
    from PIL.ImageFile import ImageFile

    global _original_methods

    if _original_methods["load"] is not None:
        ImageFile.load = _original_methods["load"]  # type: ignore

    _original_methods = {"load": None}


class PILImportHookLoader(importlib.abc.Loader):
    """Loader that applies patches after PIL is loaded."""
    
    def __init__(self, original_loader: Any) -> None:
        self.original_loader = original_loader
    
    def exec_module(self, module: Any) -> None:
        """Execute the module and then apply our patch."""
        # Let the original loader do its work
        if hasattr(self.original_loader, 'exec_module'):
            self.original_loader.exec_module(module)
        
        # Now apply our patch if this is the PIL root module
        if module.__name__ == "PIL" and not _patched:
            apply_threadsafe_patch_to_pil_image()
    
    def create_module(self, spec: Any) -> Any:
        """Delegate module creation to the original loader."""
        if hasattr(self.original_loader, 'create_module'):
            return self.original_loader.create_module(spec)
        return None


class PILImportHook(importlib.abc.MetaPathFinder):
    """MetaPathFinder that monitors PIL imports and applies patches."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._wrapped_specs: set[str] = set()

    def find_spec(
        self,
        fullname: str,
        path: Optional[list[str]] = None,
        target: Optional[object] = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        """Intercept PIL root import and wrap its loader."""
        
        # Only intercept the PIL root module
        if fullname != "PIL" or _patched or fullname in self._wrapped_specs:
            return None
        
        # Find the real spec using the rest of sys.meta_path
        for finder in sys.meta_path:
            if finder is self:
                continue
            
            spec = None
            if hasattr(finder, 'find_spec'):
                spec = finder.find_spec(fullname, path, target)
            elif hasattr(finder, 'find_module'):
                # Fallback for older finders
                loader = finder.find_module(fullname, path)
                if loader:
                    from importlib.machinery import ModuleSpec
                    spec = ModuleSpec(fullname, loader)
            
            if spec and spec.loader:
                # Wrap the loader to apply our patch after loading
                with self._lock:
                    if fullname not in self._wrapped_specs:
                        self._wrapped_specs.add(fullname)
                        spec.loader = PILImportHookLoader(spec.loader)
                        return spec
        
        return None


# Global instance of the import hook
_pil_import_hook: Optional[PILImportHook] = None


def register_pil_import_hook() -> None:
    """Register an import hook to apply thread-safety patches when PIL is imported.
    
    This function uses Python's import hook mechanism to defer patching until
    PIL is actually imported, improving startup performance when PIL is not used.
    """
    global _pil_import_hook
    
    # Check if hook is already registered
    if _pil_import_hook is not None:
        return
    
    # Check if PIL is already imported
    if "PIL" in sys.modules:
        # Already imported, apply patch immediately
        apply_threadsafe_patch_to_pil_image()
    else:
        # Register our import hook
        _pil_import_hook = PILImportHook()
        # Insert at the beginning to catch imports early
        sys.meta_path.insert(0, _pil_import_hook)


def unregister_pil_import_hook() -> None:
    """Remove the PIL import hook from sys.meta_path."""
    global _pil_import_hook
    
    if _pil_import_hook and _pil_import_hook in sys.meta_path:
        sys.meta_path.remove(_pil_import_hook)
    
    _pil_import_hook = None
