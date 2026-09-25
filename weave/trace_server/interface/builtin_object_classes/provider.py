"""Canonical location is ``weave.shared.interface.builtin_object_classes.provider``. This module is that module."""

import sys

from weave.shared.interface.builtin_object_classes import provider as _canonical
from weave.shared.interface.builtin_object_classes.provider import *  # noqa: F403

sys.modules[__name__] = _canonical
