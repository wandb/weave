"""Canonical location is ``weave.trace.refs_base``. This module is that module."""

import sys
import warnings

from weave.trace import refs_base as _canonical
from weave.trace.refs_base import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.refs is deprecated and will be removed in a future release; "
    "import weave.trace.refs_base instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
