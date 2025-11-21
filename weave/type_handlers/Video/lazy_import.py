"""Lazy import hook for MoviePy video type registration."""

import sys
from collections.abc import Sequence
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec


class MoviePyImportHook(MetaPathFinder):
    """Import hook that registers video type handler when MoviePy is imported."""

    _installed = False

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: object | None = None,
    ) -> ModuleSpec | None:
        """Check if MoviePy is being imported and trigger registration."""
        if not (fullname == "moviepy" or fullname.startswith("moviepy.")):
            return None

        # Remove ourselves from meta_path to avoid recursion
        if self in sys.meta_path:
            sys.meta_path.remove(self)

        # Trigger the video type registration
        from weave.type_handlers.Video import video

        video._ensure_registered()

        # Always return None to let the normal import mechanism handle it
        return None


def install_hook() -> None:
    """Install the MoviePy import hook."""
    if not MoviePyImportHook._installed:
        hook = MoviePyImportHook()
        sys.meta_path.insert(0, hook)
        MoviePyImportHook._installed = True
