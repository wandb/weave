"""Initialization module for Weave.

This module handles early initialization tasks for Weave.
Thread-safety patches for external libraries (PIL, moviepy) are now managed 
through the integration system and applied via autopatch.
"""

__all__: list[str] = []