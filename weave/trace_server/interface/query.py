"""Canonical location is ``weave.shared.interface.query``. This module is that module."""

import sys
import warnings

from weave.shared.interface import query as _canonical
from weave.shared.interface.query import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.interface.query is deprecated since weave 0.53.13 and will "
    "be removed in a future release.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
