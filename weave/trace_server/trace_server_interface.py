"""Canonical location is ``weave.shared.trace_server_interface``. This module is that module."""

import sys
import warnings

from weave.shared import trace_server_interface as _canonical
from weave.shared.trace_server_interface import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.trace_server_interface is deprecated since weave 0.53.13 "
    "and will be removed in a future release.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
