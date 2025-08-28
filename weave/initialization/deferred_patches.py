"""Deferred patching system that applies patches only when the target modules are imported."""

import sys
from typing import Any, Optional

from .moviepy_video_thread_safety import apply_threadsafe_patch_to_moviepy_video
from .pil_image_thread_safety import apply_threadsafe_patch_to_pil_image

_patches_installed = False


class _PatchingMetaFinder:
    """A meta path finder that applies patches when specific modules are imported."""

    def __init__(self) -> None:
        self.pil_patched = False
        self.moviepy_patched = False
        
        # Check if modules are already imported and apply patches immediately if so
        self._check_already_imported()

    def _check_already_imported(self) -> None:
        """Check if target modules are already imported and apply patches if needed."""
        # Check for PIL
        if not self.pil_patched:
            if "PIL" in sys.modules or "PIL.ImageFile" in sys.modules:
                self.pil_patched = True
                apply_threadsafe_patch_to_pil_image()
        
        # Check for moviepy
        if not self.moviepy_patched:
            if (
                "moviepy" in sys.modules
                or "moviepy.editor" in sys.modules
                or "moviepy.video.io.VideoFileClip" in sys.modules
            ):
                self.moviepy_patched = True
                apply_threadsafe_patch_to_moviepy_video()

    def find_module(
        self, fullname: str, path: Optional[list[str]] = None
    ) -> Optional[Any]:
        """Called when a module is imported to check if we need to apply patches."""
        if not self.pil_patched and fullname in ("PIL", "PIL.ImageFile"):
            self.pil_patched = True
            apply_threadsafe_patch_to_pil_image()
        elif not self.moviepy_patched and fullname in (
            "moviepy",
            "moviepy.editor",
            "moviepy.video.io.VideoFileClip",
        ):
            self.moviepy_patched = True
            apply_threadsafe_patch_to_moviepy_video()
        return None

    def find_spec(
        self,
        fullname: str,
        path: Optional[list[str]] = None,
        target: Optional[Any] = None,
    ) -> None:
        """Python 3.4+ import hook method."""
        self.find_module(fullname, path)
        return None


def ensure_patches_applied() -> None:
    """Ensure the deferred patching system is installed.
    
    This function sets up import hooks that will automatically apply
    thread-safety patches when PIL or moviepy modules are imported.
    
    If the modules are already imported when this is called, patches are
    applied immediately. Otherwise, patches are applied when the modules
    are first imported.
    
    This is idempotent - calling it multiple times has no additional effect.
    """
    global _patches_installed
    
    if _patches_installed:
        return
        
    finder = _PatchingMetaFinder()
    sys.meta_path.insert(0, finder)
    _patches_installed = True


# Install the deferred patching system when this module is imported
ensure_patches_applied()