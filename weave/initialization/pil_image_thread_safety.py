"""
This file exposes functions to make the PIL ImageFile thread-safe and revert those changes:
- `apply_threadsafe_patch_to_pil_image`
- `undo_threadsafe_patch_to_pil_image`

There is a discussion here: https://github.com/python-pillow/Pillow/issues/4848#issuecomment-671339193 in which
the author claims that the Pillow library is thread-safe. However, my reasoning leads me to a different conclusion.

Specifically, the `ImageFile.load` method is not thread-safe. This is because `load` will both close and delete
an open file handler as well as modify properties of the ImageFile object (namely the `im` property which contains
the underlying image data). Inside of Weave we use threads to parallelize work which may involve Images. This bug
has presented itself not only in our own persistence layer, but also in user code where they are consuming loaded
images across threads.

We call `apply_threadsafe_patch_to_pil_image` in the `__init__.py` file to ensure that the ImageFile class is thread-safe.
"""

import threading
from functools import wraps
from typing import Any, Callable, Optional

_patched = False
_original_methods: dict[str, Optional[Callable]] = {"load": None}
_new_lock_lock = threading.Lock()
# Global fallback lock for thread-safe image loading when per-instance locking fails
_fallback_load_lock = threading.Lock()


def apply_threadsafe_patch_to_pil_image() -> None:
    """Apply thread-safety patch to PIL ImageFile class."""
    global _patched

    if _patched:
        return

    try:
        _apply_threadsafe_patch()
    except ImportError:
        pass
    except Exception as e:
        print(f"Failed to patch PIL.ImageFile.ImageFile: Unexpected error - {e}")
    else:
        _patched = True


def _apply_threadsafe_patch() -> None:
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
                        setattr(self, "_weave_load_lock", threading.Lock())
            lock = getattr(self, "_weave_load_lock")

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

    If the patch hasn't been applied, this function does nothing.
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
        print(
            f"Failed to unpatch PIL.ImageFile.ImageFile: Unable to restore original methods - {e}"
        )
    else:
        _patched = False


def _undo_threadsafe_patch() -> None:
    from PIL.ImageFile import ImageFile

    global _original_methods

    if _original_methods["load"] is not None:
        ImageFile.load = _original_methods["load"]  # type: ignore

    _original_methods = {"load": None}
