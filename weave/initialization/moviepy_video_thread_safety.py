"""This file exposes functions to make moviepy VideoFileClip thread-safe and revert those changes:
- `apply_threadsafe_patch_to_moviepy_video`
- `undo_threadsafe_patch_to_moviepy_video`.

Similar to Pillow's ImageFile, moviepy's VideoFileClip may not be thread-safe when
loading and processing video content across multiple threads, which can lead to race conditions
and unpredictable behavior.

Inside Weave, we use threads to parallelize work which may involve Videos. This thread-safety
patch helps prevent issues when video files are accessed across threads.

We call `apply_threadsafe_patch_to_moviepy_video` in the `__init__.py` file to ensure thread-safety
for VideoFileClip loading operations.
"""

import logging
import sys
import threading
from collections.abc import Callable, Sequence
from functools import wraps
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from typing import Any

logger = logging.getLogger(__name__)

# Global state
# `_patched` is a boolean that indicates whether the thread-safety patch has been applied
# `_original_methods` is a dictionary that stores the original methods of the VideoFileClip class
# `_new_lock_lock` is a lock that is used to create a new lock for each VideoFileClip instance
# `_fallback_load_lock` is a global lock that is used to ensure thread-safe video loading when per-instance locking fails
_patched = False
_original_methods: dict[str, Callable | None] = {"__init__": None}
_new_lock_lock = threading.RLock()
_fallback_load_lock = threading.RLock()


def apply_threadsafe_patch_to_moviepy_video() -> None:
    """Apply thread-safety patch to moviepy VideoFileClip class.

    This function is idempotent - calling it multiple times has no additional effect.
    If moviepy is not installed or if patching fails, the function will handle the error gracefully.

    Note: This function now defers patching until MoviePy is actually imported to avoid
    forcing the import of MoviePy at module initialization time.
    """
    global _patched

    if _patched:
        return

    # Check if MoviePy is already imported
    import sys

    if "moviepy" in sys.modules:
        try:
            _apply_threadsafe_patch()
        except Exception as e:
            logger.info(
                f"Failed to patch moviepy.editor.VideoFileClip: Unexpected error - {e}"
            )
        else:
            _patched = True
    else:
        # Install a hook to patch when MoviePy is imported
        _install_patch_hook()


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
                        self._weave_load_lock = threading.RLock()
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


class MoviePyPatchHook(MetaPathFinder):
    """Import hook that applies thread-safety patch when MoviePy is imported."""

    _installed = False

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: object | None = None,
    ) -> ModuleSpec | None:
        """Check if MoviePy is being imported and apply patch."""
        if not (fullname == "moviepy" or fullname.startswith("moviepy.")):
            return None

        # Remove ourselves from meta_path to avoid recursion
        if self in sys.meta_path:
            sys.meta_path.remove(self)

        # Apply the thread-safety patch
        global _patched
        if _patched:
            return None
        try:
            # Import will succeed now since we're in the import process
            _apply_threadsafe_patch()
        except Exception as e:
            logger.info(
                f"Failed to patch moviepy.editor.VideoFileClip during import: {e}"
            )
        else:
            _patched = True
        # Always return None to let the normal import mechanism handle it
        return None


def _install_patch_hook() -> None:
    """Install the MoviePy patch import hook."""
    if not MoviePyPatchHook._installed:
        hook = MoviePyPatchHook()
        sys.meta_path.insert(0, hook)
        MoviePyPatchHook._installed = True
