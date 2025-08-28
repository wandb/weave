"""
DEPRECATED: This module has been refactored into weave.integrations.moviepy

This file is maintained for backward compatibility only. The thread-safety patching
functionality has been moved to the integrations system at weave.integrations.moviepy.

The functions here now delegate to the new integration system:
- `apply_threadsafe_patch_to_moviepy_video` -> uses get_moviepy_patcher().attempt_patch()
- `undo_threadsafe_patch_to_moviepy_video` -> uses get_moviepy_patcher().undo_patch()

For new code, please use the integration system directly:
```python
from weave.integrations.moviepy import get_moviepy_patcher
patcher = get_moviepy_patcher()
patcher.attempt_patch()
```
"""

import logging
from typing import Any

from weave.integrations.moviepy import get_moviepy_patcher
from weave.trace.autopatch import IntegrationSettings

logger = logging.getLogger(__name__)


def apply_threadsafe_patch_to_moviepy_video() -> None:
    """Apply thread-safety patch to moviepy VideoFileClip class.

    DEPRECATED: This function now delegates to the new integration system.
    Use `from weave.integrations.moviepy import get_moviepy_patcher` instead.

    This function is idempotent - calling it multiple times has no additional effect.
    If moviepy is not installed or if patching fails, the function will handle the error gracefully.
    """
    logger.debug(
        "Using deprecated apply_threadsafe_patch_to_moviepy_video(). "
        "Please use weave.integrations.moviepy.get_moviepy_patcher() instead."
    )
    patcher = get_moviepy_patcher(IntegrationSettings(enabled=True))
    patcher.attempt_patch()


def _apply_threadsafe_patch() -> None:
    """Internal function that performs the actual thread-safety patching of moviepy VideoFileClip.

    DEPRECATED: This function is no longer used. The patching logic has been moved
    to weave.integrations.moviepy.MoviePyPatcher.

    Raises:
        ImportError: If moviepy is not installed
        Exception: For any other unexpected errors during patching
    """
    # This function is kept for backward compatibility but no longer does anything
    # The actual patching is handled by the integration system
    pass


def undo_threadsafe_patch_to_moviepy_video() -> None:
    """Revert the thread-safety patch applied to moviepy VideoFileClip class.

    DEPRECATED: This function now delegates to the new integration system.
    Use `from weave.integrations.moviepy import get_moviepy_patcher` instead.

    This function is idempotent - if the patch hasn't been applied, this function does nothing.
    If the patch has been applied but can't be reverted, an error message is printed.
    """
    logger.debug(
        "Using deprecated undo_threadsafe_patch_to_moviepy_video(). "
        "Please use weave.integrations.moviepy.get_moviepy_patcher() instead."
    )
    patcher = get_moviepy_patcher()
    patcher.undo_patch()


def _undo_threadsafe_patch() -> None:
    """Internal function that performs the actual removal of thread-safety patches.

    DEPRECATED: This function is no longer used. The unpatching logic has been moved
    to weave.integrations.moviepy.MoviePyPatcher.

    Raises:
        ImportError: If moviepy is not installed
        Exception: For any other unexpected errors during unpatching
    """
    # This function is kept for backward compatibility but no longer does anything
    # The actual unpatching is handled by the integration system
    pass
