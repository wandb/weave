"""Canonical location is ``weave.shared.constants``. This module re-exports it."""

import warnings

from weave.shared.constants import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.constants is deprecated since weave 0.53.13 and will be "
    "removed after weave 0.53.13; import weave.shared.constants instead.",
    FutureWarning,
    stacklevel=2,
)
