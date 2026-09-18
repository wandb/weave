"""Canonical location is ``weave.shared.interface.builtin_object_classes.saved_view``. This module is that module."""

import sys

from weave.shared.interface.builtin_object_classes import saved_view as _canonical
from weave.shared.interface.builtin_object_classes.saved_view import *  # noqa: F403

sys.modules[__name__] = _canonical
