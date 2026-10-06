"""Canonical location is ``weave.shared.interface.builtin_object_classes.test_only_example``. This module is that module."""

import sys

from weave.shared.interface.builtin_object_classes import (
    test_only_example as _canonical,
)
from weave.shared.interface.builtin_object_classes.test_only_example import *  # noqa: F403

sys.modules[__name__] = _canonical
