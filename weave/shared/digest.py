"""Canonical location is ``weave.trace.serialization.digest``. This module is that module."""

import sys
import warnings

from weave.trace.serialization import digest as _canonical
from weave.trace.serialization.digest import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.digest is deprecated and will be removed in a future release;"
    " import weave.trace.serialization.digest instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
