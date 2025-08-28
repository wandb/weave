"""Thread-safety patching integration for moviepy library.

This integration ensures thread-safe video loading operations in moviepy VideoFileClip class.
Similar to Pillow's ImageFile, moviepy's VideoFileClip may not be thread-safe when
loading and processing video content across multiple threads, which can lead to race conditions
and unpredictable behavior.

Inside Weave, we use threads to parallelize work which may involve Videos. This thread-safety
patch helps prevent issues when video files are accessed across threads.
"""

import logging
import threading
from functools import wraps
from typing import Any, Callable, Optional

from weave.integrations.patcher import Patcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings

logger = logging.getLogger(__name__)

# Global state for the thread-safety patching
_new_lock_lock = threading.RLock()
_fallback_load_lock = threading.RLock()


class MoviePyPatcher(Patcher):
    """Patcher for moviepy library to ensure thread-safe video loading."""

    def __init__(self, settings: Optional[IntegrationSettings] = None) -> None:
        self.settings = settings or IntegrationSettings()
        self._patched = False
        self._original_methods: dict[str, Optional[Callable]] = {"__init__": None}
        self._patcher: Optional[SymbolPatcher] = None

    def attempt_patch(self) -> bool:
        """Apply thread-safety patch to moviepy VideoFileClip class."""
        if not self.settings.enabled:
            return False

        if self._patched:
            return True

        try:
            from moviepy.editor import VideoFileClip

            # Store original method
            self._original_methods["__init__"] = VideoFileClip.__init__

            # Create the patcher using SymbolPatcher
            self._patcher = SymbolPatcher(
                get_base_symbol=lambda: VideoFileClip,
                attribute_name="__init__",
                make_new_value=self._make_thread_safe_init,
            )

            if self._patcher.attempt_patch():
                self._patched = True
                return True
            return False

        except ImportError:
            logger.debug("moviepy not installed, skipping moviepy patching")
            return False
        except Exception as e:
            logger.debug(f"Failed to patch moviepy.editor.VideoFileClip: {e}")
            return False

    def undo_patch(self) -> bool:
        """Revert the thread-safety patch applied to moviepy VideoFileClip class."""
        if not self._patched:
            return True

        if self._patcher:
            result = self._patcher.undo_patch()
            if result:
                self._patched = False
            return result
        return False

    def _make_thread_safe_init(self, original_init: Callable) -> Callable:
        """Create a thread-safe wrapper for the VideoFileClip.__init__ method."""

        @wraps(original_init)
        def thread_safe_init(self: Any, *args: Any, **kwargs: Any) -> Any:
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
                return original_init(self, *args, **kwargs)

        return thread_safe_init


# Global patcher instance
_moviepy_patcher: Optional[MoviePyPatcher] = None


def get_moviepy_patcher(
    settings: Optional[IntegrationSettings] = None,
) -> MoviePyPatcher:
    """Get the global moviepy patcher instance."""
    global _moviepy_patcher
    if _moviepy_patcher is None:
        _moviepy_patcher = MoviePyPatcher(settings)
    return _moviepy_patcher