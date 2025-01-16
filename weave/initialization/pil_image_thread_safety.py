"""
This file exposes a function that makes the PIL ImageFile thread-safe: `make_image_file_thread_safe`.

There is a discussion here: https://github.com/python-pillow/Pillow/issues/4848#issuecomment-671339193 in which
the author claims that the Pillow library is thread-safe. However, my reasoning leads me to a different conclusion.

Specifically, the `ImageFile.load` method is not thread-safe. This is because `load` will both close and delete
an open file handler as well as modify properties of the ImageFile object (namely the `im` property which contains
the underlying image data). Inside of Weave we use threads to parallelize work which may involve Images. This bug
has presented itself not only in our own persistence layer, but also in user code where they are consuming loaded
images across threads.

We call `make_image_file_thread_safe` in the `__init__.py` file to ensure that the ImageFile class is thread-safe.
"""

import threading
from functools import wraps

_patched = False


def make_image_file_thread_safe() -> None:
    global _patched
    try:
        _make_image_file_thread_safe()
    except Exception as e:
        print(f"Failed to patch PIL.ImageFile.ImageFile: {e}.")
    else:
        _patched = True


def _make_image_file_thread_safe() -> None:
    from PIL.ImageFile import ImageFile

    old_load = ImageFile.load
    old_init = ImageFile.__init__

    @wraps(old_init)
    def new_init(self, *args, **kwargs):  # type: ignore
        self._weave_load_lock = threading.Lock()
        return old_init(self, *args, **kwargs)

    @wraps(old_load)
    def new_load(self, *args, **kwargs):  # type: ignore
        with self._weave_load_lock:
            return old_load(self, *args, **kwargs)

    ImageFile.__init__ = new_init  # type: ignore
    ImageFile.load = new_load  # type: ignore
