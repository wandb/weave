"""Thread-safety patching integration for PIL (Pillow) library.

This integration ensures thread-safe image loading operations in PIL ImageFile class.
The PIL ImageFile.load method is not thread-safe because it:
1. Closes and deletes an open file handler
2. Modifies properties of the ImageFile object (namely the `im` property which contains the underlying image data)

Inside Weave, we use threads to parallelize work which may involve Images. This thread-safety issue has manifested
not only in our persistence layer but also in user code where loaded images are accessed across threads.
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


class PILPatcher(Patcher):
    """Patcher for PIL (Pillow) library to ensure thread-safe image loading."""

    def __init__(self, settings: Optional[IntegrationSettings] = None) -> None:
        self.settings = settings or IntegrationSettings()
        self._patched = False
        self._original_methods: dict[str, Optional[Callable]] = {"load": None}
        self._patcher: Optional[SymbolPatcher] = None

    def attempt_patch(self) -> bool:
        """Apply thread-safety patch to PIL ImageFile class."""
        if not self.settings.enabled:
            return False

        if self._patched:
            return True

        try:
            from PIL.ImageFile import ImageFile

            # Store original method
            self._original_methods["load"] = ImageFile.load

            # Create the patcher using SymbolPatcher
            self._patcher = SymbolPatcher(
                get_base_symbol=lambda: ImageFile,
                attribute_name="load",
                make_new_value=self._make_thread_safe_load,
            )

            if self._patcher.attempt_patch():
                self._patched = True
                return True
            return False  # noqa: TRY300

        except ImportError:
            logger.debug("PIL not installed, skipping PIL patching")
            return False
        except Exception as e:
            logger.debug(f"Failed to patch PIL.ImageFile.ImageFile: {e}")
            return False

    def undo_patch(self) -> bool:
        """Revert the thread-safety patch applied to PIL ImageFile class."""
        if not self._patched:
            return True

        if self._patcher:
            result = self._patcher.undo_patch()
            if result:
                self._patched = False
            return result
        return False

    def _make_thread_safe_load(self, original_load: Callable) -> Callable:
        """Create a thread-safe wrapper for the ImageFile.load method."""

        @wraps(original_load)
        def thread_safe_load(self: Any, *args: Any, **kwargs: Any) -> Any:
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
                return original_load(self, *args, **kwargs)

        return thread_safe_load


# Global patcher instance
_pil_patcher: Optional[PILPatcher] = None


def get_pil_patcher(settings: Optional[IntegrationSettings] = None) -> PILPatcher:
    """Get the global PIL patcher instance."""
    global _pil_patcher
    if _pil_patcher is None:
        _pil_patcher = PILPatcher(settings)
    return _pil_patcher
