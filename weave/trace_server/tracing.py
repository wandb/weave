"""Canonical location is ``weave.trace.server_tracing``. This module is that module."""

import sys
import warnings

from weave.trace import server_tracing as _canonical
from weave.trace.server_tracing import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.tracing is deprecated since weave 0.53.13 and will be "
    "removed in a future release; import weave.trace.server_tracing instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
