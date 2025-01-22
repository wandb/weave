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
    _new_lock_lock = threading.Lock()

    @wraps(old_load)
    def new_load(self: ImageFile, *args: Any, **kwargs: Any) -> Any:
        # Get a lock for this specific ImageFile instance using its ID
        lock = None
        try:
            if not hasattr(self, "_weave_load_lock"):
                with _new_lock_lock:
                    setattr(self, "_weave_load_lock", threading.Lock())
            lock = getattr(self, "_weave_load_lock")
        except Exception:
            return old_load(self, *args, **kwargs)
        if lock is None:
            return old_load(self, *args, **kwargs)
        with lock:
            return old_load(self, *args, **kwargs)

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
