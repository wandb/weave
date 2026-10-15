"""Canonical location is ``weave.trace.serialization.object_class_util``. This module is that module."""

import sys
import warnings

from weave.trace.serialization import object_class_util as _canonical
from weave.trace.serialization.object_class_util import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.object_class_util is deprecated and will be removed in a "
    "future release; import weave.trace.serialization.object_class_util "
    "instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
