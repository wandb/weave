"""Canonical location is ``weave.shared.interface.builtin_object_classes.annotation_spec``. This module is that module."""

import sys

from weave.shared.interface.builtin_object_classes import annotation_spec as _canonical
from weave.shared.interface.builtin_object_classes.annotation_spec import *  # noqa: F403

sys.modules[__name__] = _canonical
