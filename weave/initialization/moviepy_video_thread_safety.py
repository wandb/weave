"""
This file exposes functions to make moviepy VideoFileClip thread-safe and revert those changes:
- `apply_threadsafe_patch_to_moviepy_video`
- `undo_threadsafe_patch_to_moviepy_video`
- `register_moviepy_import_hook` - Deferred patching using importlib MetaPathFinder

Similar to Pillow's ImageFile, moviepy's VideoFileClip may not be thread-safe when
loading and processing video content across multiple threads, which can lead to race conditions
and unpredictable behavior.

Inside Weave, we use threads to parallelize work which may involve Videos. This thread-safety
patch helps prevent issues when video files are accessed across threads.

We use a MetaPathFinder to defer patching until moviepy is actually imported, improving startup performance.
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
# `_original_methods` is a dictionary that stores the original methods of the VideoFileClip class
# `_new_lock_lock` is a lock that is used to create a new lock for each VideoFileClip instance
# `_fallback_load_lock` is a global lock that is used to ensure thread-safe video loading when per-instance locking fails
_patched = False
_original_methods: dict[str, Optional[Callable]] = {"__init__": None}
_new_lock_lock = threading.RLock()
_fallback_load_lock = threading.RLock()


def apply_threadsafe_patch_to_moviepy_video() -> None:
    """Apply thread-safety patch to moviepy VideoFileClip class.

    This function is idempotent - calling it multiple times has no additional effect.
    If moviepy is not installed or if patching fails, the function will handle the error gracefully.
    
    Note: This function assumes moviepy is already imported and will import moviepy.editor
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
        logger.info(
            f"Failed to patch moviepy.editor.VideoFileClip: Unexpected error - {e}"
        )
    else:
        _patched = True


def _apply_threadsafe_patch() -> None:
    """Internal function that performs the actual thread-safety patching of moviepy VideoFileClip.

    This imports moviepy.editor and applies the patch. Should only be called when
    moviepy is already imported.

    Raises:
        ImportError: If moviepy is not installed
        Exception: For any other unexpected errors during patching
    """
    # Only import when we're actually applying the patch
    # This ensures we don't eagerly load moviepy
    from moviepy.editor import VideoFileClip

    global _original_methods

    # Store original methods
    _original_methods["__init__"] = VideoFileClip.__init__
    old_init = VideoFileClip.__init__

    @wraps(old_init)
    def new_init(self: VideoFileClip, *args: Any, **kwargs: Any) -> Any:
        # This function wraps moviepy's VideoFileClip.__init__ method to make it thread-safe
        # by ensuring only one thread can initialize a video at a time per VideoFileClip instance.

        # We use a per-instance lock to allow concurrent loading of different videos
        # while preventing concurrent access to the same video.
        try:
            # Create a new lock for this VideoFileClip instance if it doesn't exist.
            # The lock creation itself needs to be thread-safe, hence _new_lock_lock.
            if not hasattr(self, "_weave_load_lock"):
                with _new_lock_lock:
                    # Double-check pattern: verify the attribute still doesn't exist
                    # after acquiring the lock to prevent race conditions
                    if not hasattr(self, "_weave_load_lock"):
                        setattr(self, "_weave_load_lock", threading.RLock())
            lock = self._weave_load_lock

        except Exception:
            # If anything goes wrong with the locking mechanism,
            # fall back to the global lock for safety
            lock = _fallback_load_lock

        # Acquire the instance-specific lock before initializing the video
        # This ensures thread-safety during the entire initialization process
        with lock:
            return old_init(self, *args, **kwargs)

    # Replace the __init__ method with our thread-safe version
    VideoFileClip.__init__ = new_init  # type: ignore


def undo_threadsafe_patch_to_moviepy_video() -> None:
    """Revert the thread-safety patch applied to moviepy VideoFileClip class.

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
            f"Failed to unpatch moviepy.editor.VideoFileClip: Unable to restore original methods - {e}"
        )
    else:
        _patched = False


def _undo_threadsafe_patch() -> None:
    """Internal function that performs the actual removal of thread-safety patches.

    Raises:
        ImportError: If moviepy is not installed
        Exception: For any other unexpected errors during unpatching
    """
    from moviepy.editor import VideoFileClip

    global _original_methods

    if _original_methods["__init__"] is not None:
        VideoFileClip.__init__ = _original_methods["__init__"]  # type: ignore

    _original_methods = {"__init__": None}


class MoviePyImportHookLoader(importlib.abc.Loader):
    """Loader that applies patches after moviepy is loaded."""
    
    def __init__(self, original_loader: Any) -> None:
        self.original_loader = original_loader
    
    def exec_module(self, module: Any) -> None:
        """Execute the module and then apply our patch."""
        # Let the original loader do its work
        if hasattr(self.original_loader, 'exec_module'):
            self.original_loader.exec_module(module)
        
        # Now apply our patch if this is the moviepy root module
        if module.__name__ == "moviepy" and not _patched:
            apply_threadsafe_patch_to_moviepy_video()
    
    def create_module(self, spec: Any) -> Any:
        """Delegate module creation to the original loader."""
        if hasattr(self.original_loader, 'create_module'):
            return self.original_loader.create_module(spec)
        return None


class MoviePyImportHook(importlib.abc.MetaPathFinder):
    """MetaPathFinder that monitors moviepy imports and applies patches."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._wrapped_specs: set[str] = set()

    def find_spec(
        self,
        fullname: str,
        path: Optional[list[str]] = None,
        target: Optional[object] = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        """Intercept moviepy root import and wrap its loader."""
        
        # Only intercept the moviepy root module
        if fullname != "moviepy" or _patched or fullname in self._wrapped_specs:
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
                        spec.loader = MoviePyImportHookLoader(spec.loader)
                        return spec
        
        return None


# Global instance of the import hook
_moviepy_import_hook: Optional[MoviePyImportHook] = None


def register_moviepy_import_hook() -> None:
    """Register an import hook to apply thread-safety patches when moviepy is imported.
    
    This function uses Python's import hook mechanism to defer patching until
    moviepy is actually imported, improving startup performance when moviepy is not used.
    """
    global _moviepy_import_hook
    
    # Check if hook is already registered
    if _moviepy_import_hook is not None:
        return
    
    # Check if moviepy is already imported
    if "moviepy" in sys.modules:
        # Already imported, apply patch immediately
        apply_threadsafe_patch_to_moviepy_video()
    else:
        # Register our import hook
        _moviepy_import_hook = MoviePyImportHook()
        # Insert at the beginning to catch imports early
        sys.meta_path.insert(0, _moviepy_import_hook)


def unregister_moviepy_import_hook() -> None:
    """Remove the moviepy import hook from sys.meta_path."""
    global _moviepy_import_hook
    
    if _moviepy_import_hook and _moviepy_import_hook in sys.meta_path:
        sys.meta_path.remove(_moviepy_import_hook)
    
    _moviepy_import_hook = None
