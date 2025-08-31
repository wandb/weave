"""Deferred patching system for moviepy thread safety."""

import importlib.abc
import importlib.machinery
import sys
from typing import Optional, Sequence, Union

_moviepy_patch_installed = False


class _MoviePyPatchingMetaFinder(importlib.abc.MetaPathFinder):
    """Meta path finder that applies thread-safety patch when moviepy is imported."""

    def __init__(self) -> None:
        self.patched = False
        # Check if moviepy is already imported
        if (
            "moviepy" in sys.modules
            or "moviepy.editor" in sys.modules
            or "moviepy.video.io.VideoFileClip" in sys.modules
        ):
            self._apply_patch()

    def _apply_patch(self) -> None:
        """Apply the thread-safety patch to moviepy if not already applied."""
        if not self.patched:
            self.patched = True
            from weave.initialization.moviepy_video_thread_safety import (
                apply_threadsafe_patch_to_moviepy_video,
            )
            apply_threadsafe_patch_to_moviepy_video()

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[Union[bytes, str]]] = None,
        target: Optional[object] = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        """Apply patch when moviepy modules are imported."""
        if not self.patched and fullname in (
            "moviepy",
            "moviepy.editor",
            "moviepy.video.io.VideoFileClip",
        ):
            self._apply_patch()
        return None


def ensure_moviepy_patch_installed() -> None:
    """Install the moviepy patching import hook if not already installed.
    
    This function sets up an import hook that will automatically apply
    thread-safety patches when moviepy is imported. If moviepy is already 
    imported when this is called, the patch is applied immediately.
    
    This is idempotent - calling it multiple times has no additional effect.
    """
    global _moviepy_patch_installed
    if not _moviepy_patch_installed:
        finder = _MoviePyPatchingMetaFinder()
        sys.meta_path.insert(0, finder)
        _moviepy_patch_installed = True