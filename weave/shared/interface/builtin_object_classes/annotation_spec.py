"""Canonical location is ``weave.trace.builtin_object_classes.annotation_spec``. This module is that module."""

import sys
import warnings

from weave.trace.builtin_object_classes import annotation_spec as _canonical
from weave.trace.builtin_object_classes.annotation_spec import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.interface.builtin_object_classes.annotation_spec is "
    "deprecated and will be removed in a future release; import "
    "weave.trace.builtin_object_classes.annotation_spec instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
