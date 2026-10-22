"""Canonical location is ``weave.trace.refs_internal``. This module is that module."""

import sys
import warnings

from weave.trace import refs_internal as _canonical
from weave.trace.refs_internal import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.refs_internal is deprecated and will be removed in a future "
    "release; import weave.trace.refs_internal instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
