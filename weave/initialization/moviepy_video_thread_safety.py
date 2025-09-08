"""
This file exposes functions to make moviepy VideoFileClip thread-safe and revert those changes:
- `apply_threadsafe_patch_to_moviepy_video`
- `undo_threadsafe_patch_to_moviepy_video`
- `install_moviepy_import_hook`

Similar to Pillow's ImageFile, moviepy's VideoFileClip may not be thread-safe when
loading and processing video content across multiple threads, which can lead to race conditions
and unpredictable behavior.

Inside Weave, we use threads to parallelize work which may involve Videos. This thread-safety
patch helps prevent issues when video files are accessed across threads.

We call `install_moviepy_import_hook` in the `__init__.py` file to defer patching until moviepy
is actually imported by the user.
"""

import importlib.util
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

    Raises:
        ImportError: If moviepy is not installed
        Exception: For any other unexpected errors during patching
    """
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


def install_moviepy_import_hook() -> None:
    """Install an import hook that patches moviepy when it's first imported.
    
    This allows us to defer the patching until moviepy is actually needed,
    rather than trying to patch it eagerly during weave initialization.
    """
    global _patched
    
    # Don't install the hook if we've already patched
    if _patched:
        return
    
    # Check if moviepy.editor is already imported
    if "moviepy.editor" in sys.modules:
        # If it's already imported, patch it immediately
        apply_threadsafe_patch_to_moviepy_video()
        return
    
    # Install the import hook using importlib machinery
    # Handle both module and dict forms of __builtins__
    if isinstance(__builtins__, dict):
        original_import = __builtins__["__import__"]
    else:
        original_import = __builtins__.__import__
    
    def patching_import(name, *args, **kwargs):
        module = original_import(name, *args, **kwargs)
        
        # Check if moviepy.editor was just imported
        if name == "moviepy.editor" or (name == "moviepy" and "moviepy.editor" in sys.modules):
            # Apply the patch now that moviepy is available
            apply_threadsafe_patch_to_moviepy_video()
        
        return module
    
    # Replace the built-in import function
    if isinstance(__builtins__, dict):
        __builtins__["__import__"] = patching_import
    else:
        __builtins__.__import__ = patching_import
