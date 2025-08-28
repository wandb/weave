"""Initialization module for Weave.

This module handles early initialization tasks, including applying thread-safety patches
to external libraries via the integration system.

The thread-safety patches for PIL and moviepy have been moved to the integrations system
for consistency with other library patches. They are now managed through:
- weave.integrations.pil
- weave.integrations.moviepy

These patches are automatically applied when autopatch is called with appropriate settings.
"""

from weave.integrations.moviepy import get_moviepy_patcher
from weave.integrations.pil import get_pil_patcher
from weave.trace.autopatch import IntegrationSettings

# For backward compatibility, apply the patches here directly
# These are now properly integrated into the autopatch system
# but we maintain this for any code that imports from initialization
get_pil_patcher(IntegrationSettings(enabled=True)).attempt_patch()
get_moviepy_patcher(IntegrationSettings(enabled=True)).attempt_patch()

__all__: list[str] = []
