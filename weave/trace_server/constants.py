"""Canonical location is ``weave.trace.constants``. This module re-exports it."""

import warnings

from weave.trace.constants import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.constants is deprecated since weave 0.53.13 and will be"
    " removed in a future release; import weave.trace.constants instead.",
    FutureWarning,
    stacklevel=2,
)
