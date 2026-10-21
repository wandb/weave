"""Canonical location is ``weave.trace.constants``. This module is that module."""

import sys
import warnings

from weave.trace import constants as _canonical
from weave.trace.constants import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.constants is deprecated and will be removed in a future "
    "release; import weave.trace.constants instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
