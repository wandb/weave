"""Canonical location is ``weave.trace.serialization.serialization_metadata``. This module is that module."""

import sys
import warnings

from weave.trace.serialization import serialization_metadata as _canonical
from weave.trace.serialization.serialization_metadata import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.serialization_metadata is deprecated and will be removed in a"
    " future release; import weave.trace.serialization.serialization_metadata "
    "instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
