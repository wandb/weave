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
from weakref import WeakKeyDictionary

_patched = False
_original_methods: dict[str, Optional[Callable]] = {"load": None}


class TheadSafeLockLookup:
    global_lock: threading.Lock
    lock_map: WeakKeyDictionary[Any, threading.Lock]

    def __init__(self) -> None:
        self.global_lock = threading.Lock()
        self.lock_map = WeakKeyDictionary()

    def get_lock(self, obj: Any) -> threading.Lock:
        with self.global_lock:
            if obj not in self.lock_map:
                self.lock_map[obj] = threading.Lock()
            return self.lock_map[obj]


_global_thread_safe_lock_lookup = TheadSafeLockLookup()


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
        # There is an edge case at play here: If the ImageFile is constructed
        # before patching (ie import weave), then the ImageFile will not have
        # the _weave_load_lock attribute and this will raise an AttributeError.
        # To avoid this, we check for the existence of the _weave_load_lock
        # attribute before acquiring the lock.
        #
        # Unfortunately, this means in these cases, the ImageFile will not be
        # thread-safe.
        if not hasattr(self, "_weave_load_lock"):
            self._weave_load_lock = _global_thread_safe_lock_lookup.get_lock(self)  # type: ignore
        with self._weave_load_lock:  # type: ignore
            return old_load(self, *args, **kwargs)

    # ImageFile.__init__ = new_init  # type: ignore
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
