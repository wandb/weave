"""
This file exposes functions to make the PIL ImageFile thread-safe and revert those changes:
- `apply_threadsafety_patch_to_pil_image`
- `undo_threadsafety_patch_to_pil_image`

There is a discussion here: https://github.com/python-pillow/Pillow/issues/4848#issuecomment-671339193 in which
the author claims that the Pillow library is thread-safe. However, my reasoning leads me to a different conclusion.

Specifically, the `ImageFile.load` method is not thread-safe. This is because `load` will both close and delete
an open file handler as well as modify properties of the ImageFile object (namely the `im` property which contains
the underlying image data). Inside of Weave we use threads to parallelize work which may involve Images. This bug
has presented itself not only in our own persistence layer, but also in user code where they are consuming loaded
images across threads.

We call `apply_threadsafety_patch_to_pil_image` in the `__init__.py` file to ensure that the ImageFile class is thread-safe.
"""

import threading
from functools import wraps
from typing import Any, Optional

_patched = False
_original_methods: dict[str, Optional[callable]] = {"init": None, "load": None}


def apply_threadsafety_patch_to_pil_image() -> None:
    """Apply thread-safety patch to PIL ImageFile class."""
    global _patched

    if _patched:
        return

    try:
        _apply_threadsafety_patch()
    except ImportError:
        pass
    except Exception as e:
        print(f"Failed to patch PIL.ImageFile.ImageFile: Unexpected error - {e}")
    else:
        _patched = True


def _apply_threadsafety_patch() -> None:
    from PIL.ImageFile import ImageFile

    global _original_methods

    # Store original methods
    _original_methods["init"] = ImageFile.__init__
    _original_methods["load"] = ImageFile.load

    old_load = ImageFile.load
    old_init = ImageFile.__init__

    @wraps(old_init)
    def new_init(self: ImageFile, *args: Any, **kwargs: Any) -> None:
        self._weave_load_lock = threading.Lock()
        return old_init(self, *args, **kwargs)

    @wraps(old_load)
    def new_load(self: ImageFile, *args: Any, **kwargs: Any) -> None:
        with self._weave_load_lock:
            return old_load(self, *args, **kwargs)

    ImageFile.__init__ = new_init  # type: ignore
    ImageFile.load = new_load  # type: ignore


def undo_threadsafety_patch_to_pil_image() -> None:
    """Revert the thread-safety patch applied to PIL ImageFile class.

    If the patch hasn't been applied, this function does nothing.
    If the patch has been applied but can't be reverted, an error message is printed.
    """
    from PIL.ImageFile import ImageFile

    global _patched, _original_methods

    if not _patched:
        return

    try:
        if _original_methods["init"] is not None:
            ImageFile.__init__ = _original_methods["init"]  # type: ignore
        if _original_methods["load"] is not None:
            ImageFile.load = _original_methods["load"]  # type: ignore

        _original_methods = {"init": None, "load": None}
        _patched = False
    except Exception as e:
        print(
            f"Failed to unpatch PIL.ImageFile.ImageFile: Unable to restore original methods - {e}"
        )
