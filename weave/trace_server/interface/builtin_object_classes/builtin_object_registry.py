"""Canonical location is ``weave.shared.interface.builtin_object_classes.builtin_object_registry``. This module is that module."""

import sys

from weave.shared.interface.builtin_object_classes import (
    builtin_object_registry as _canonical,
)

sys.modules[__name__] = _canonical
