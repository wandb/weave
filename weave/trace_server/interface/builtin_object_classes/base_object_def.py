"""Canonical location is ``weave.shared.interface.builtin_object_classes.base_object_def``. This module is that module."""

import sys

from weave.shared.interface.builtin_object_classes import base_object_def as _canonical
from weave.shared.interface.builtin_object_classes.base_object_def import *  # noqa: F403

sys.modules[__name__] = _canonical
